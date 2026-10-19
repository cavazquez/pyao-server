"""WSS binario como stream AO: comparte sesión, framer, límites y cierre nativos."""

import asyncio
import contextlib
from typing import TYPE_CHECKING, cast
from urllib.parse import urlsplit

from websockets.asyncio.server import Server, ServerConnection, serve
from websockets.exceptions import ConnectionClosed
from websockets.typing import Origin

if TYPE_CHECKING:
    import ssl
    from collections.abc import Awaitable, Callable

MAX_MESSAGE_BYTES = 65536


class WebSocketWriter:
    """Interfaz de StreamWriter con envío binario y contrapresión acotada."""

    def __init__(self, connection: ServerConnection) -> None:
        """El buffer pertenece exclusivamente a esta conexión."""
        self.connection = connection
        self.pending = bytearray()
        self.closing = False
        self.close_task: asyncio.Task[None] | None = None

    def get_extra_info(self, name: str, default: object = None) -> object:
        """Conserva dirección y contexto TLS para la admisión/autenticación común.

        Returns:
            Metadato original del transporte; nunca deriva IP de cabeceras del cliente.
        """
        if name == "peername":
            return self.connection.remote_address
        return cast("object", self.connection.transport.get_extra_info(name, default))

    def write(self, data: bytes) -> None:
        """Encola un envío limitado hasta drain.

        Raises:
            ConnectionError: Por transporte cerrado o buffer excesivo.
        """
        if self.closing or len(self.pending) + len(data) > MAX_MESSAGE_BYTES:
            message = "Transporte WebSocket cerrado o cola de envío excedida"
            raise ConnectionError(message)
        self.pending.extend(data)

    async def drain(self) -> None:
        """Espera el envío y la contrapresión del transporte WebSocket.

        Raises:
            ConnectionError: Si el peer se cerró durante el envío.
        """
        if self.pending:
            data = bytes(self.pending)
            self.pending.clear()
            try:
                await self.connection.send(data)
            except ConnectionClosed as exc:
                message = "La conexión WSS se cerró durante el envío"
                raise ConnectionError(message) from exc

    def is_closing(self) -> bool:
        """Indica si comenzó el cierre.

        Returns:
            Estado local del cierre, estable entre llamadas.
        """
        return self.closing

    def close(self) -> None:
        """Inicia una sola vez el handshake de cierre propiedad del adaptador."""
        if not self.closing:
            self.closing = True
            self.close_task = asyncio.create_task(self.connection.close(), name="wss-close")

    async def wait_closed(self) -> None:
        """Espera la liberación del socket antes de abandonar el handler."""
        if self.close_task:
            await self.close_task
        await self.connection.wait_closed()


async def start_websocket(
    handler: Callable[[asyncio.StreamReader, asyncio.StreamWriter], Awaitable[None]],
    host: str,
    port: int,
    origins: list[str],
    context: ssl.SSLContext | None,
    *,
    tls_proxy: bool = False,
) -> Server:
    """Inicia un endpoint optativo: WSS directo o proxy TLS explícito en loopback.

    Returns:
        Listener con cierre/drain propio del servidor.

    Raises:
        ValueError: Sin orígenes HTTPS válidos, TLS ni proxy local explícito.
    """
    if not origins or any(
        urlsplit(origin).scheme != "https" or not urlsplit(origin).netloc or "*" in origin
        for origin in origins
    ):
        message = "WSS requiere una lista explícita de orígenes HTTPS"
        raise ValueError(message)
    if context is None and not (tls_proxy and host in {"127.0.0.1", "::1", "localhost"}):
        message = "WSS requiere TLS directo o un proxy TLS explícito con backend en loopback"
        raise ValueError(message)

    async def connected(connection: ServerConnection) -> None:
        reader = asyncio.StreamReader(limit=MAX_MESSAGE_BYTES)
        writer = WebSocketWriter(connection)

        async def receive() -> None:
            try:
                async for data in connection:
                    if not isinstance(data, bytes):
                        await connection.close(
                            code=1003, reason="Sólo se acepta protocolo AO binario"
                        )
                        return
                    reader.feed_data(data)
                    # El framer AO comparte el límite de memoria nativo. Evitar
                    # alimentar un StreamReader pausado por un consumidor lento.
                    while len(reader._buffer) >= MAX_MESSAGE_BYTES:  # type: ignore[attr-defined]  # ruff: ignore[private-member-access] - buffer del puente productor/consumidor.
                        await asyncio.sleep(0.01)
                        if writer.closing:
                            return
            except ConnectionClosed:
                pass
            finally:
                reader.feed_eof()

        incoming = asyncio.create_task(receive(), name="wss-stream-reader")
        try:
            await handler(reader, cast("asyncio.StreamWriter", writer))
        finally:
            writer.close()
            incoming.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await incoming
            await writer.wait_closed()

    return await serve(
        connected,
        host,
        port,
        ssl=context,
        origins=[Origin(value) for value in origins],
        max_size=MAX_MESSAGE_BYTES,
        max_queue=8,
        write_limit=32768,
        open_timeout=10,
        close_timeout=5,
        compression=None,
        server_header=None,
    )
