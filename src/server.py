"""Servidor TCP para Argentum Online."""

import asyncio
import logging

logger = logging.getLogger(__name__)


class ArgentumServer:
    """Servidor TCP para Argentum Online."""

    def __init__(self, host: str = "0.0.0.0", port: int = 7666) -> None:
        """Inicializa el servidor.

        Args:
            host: Dirección IP donde escuchar.
            port: Puerto donde escuchar.
        """
        self.host = host
        self.port = port
        self.server: asyncio.Server | None = None

    async def handle_client(  # noqa: PLR6301
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        """Maneja la conexión de un cliente.

        Args:
            reader: Stream para leer datos del cliente.
            writer: Stream para escribir datos al cliente.
        """
        addr = writer.get_extra_info("peername")
        logger.info("Nueva conexión desde %s", addr)

        try:
            while True:
                data = await reader.read(1024)
                if not data:
                    break

                logger.info("Recibidos %d bytes desde %s", len(data), addr)
                # Por ahora solo logueamos los datos recibidos

        except Exception:
            logger.exception("Error manejando cliente %s", addr)
        finally:
            logger.info("Cerrando conexión con %s", addr)
            writer.close()
            await writer.wait_closed()

    async def start(self) -> None:
        """Inicia el servidor TCP."""
        self.server = await asyncio.start_server(
            self.handle_client,
            self.host,
            self.port,
        )

        addrs = ", ".join(str(sock.getsockname()) for sock in self.server.sockets)
        logger.info("Servidor escuchando en %s", addrs)

        async with self.server:
            await self.server.serve_forever()

    async def stop(self) -> None:
        """Detiene el servidor."""
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            logger.info("Servidor detenido")
