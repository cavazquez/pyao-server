"""Manejo de conexiones de cliente."""

import asyncio
import logging

logger = logging.getLogger(__name__)


class ClientConnection:
    """Encapsula la conexión con un cliente y provee métodos para comunicación."""

    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        """Inicializa la conexión del cliente.

        Args:
            reader: Stream para leer datos del cliente.
            writer: Stream para enviar datos al cliente.
        """
        self.reader = reader
        self.writer = writer
        self.address = writer.get_extra_info("peername")
        self.is_ssl_enabled = writer.get_extra_info("ssl_object") is not None

    async def send(self, data: bytes) -> None:
        """Envía datos al cliente.

        Args:
            data: Bytes a enviar al cliente.
        """
        self.writer.write(data)
        await self.writer.drain()
        logger.debug("Enviados %d bytes a %s", len(data), self.address)

    async def receive(self, max_bytes: int = 1024) -> bytes:
        """Recibe datos del cliente.

        Args:
            max_bytes: Número máximo de bytes a leer.

        Returns:
            Bytes recibidos del cliente (vacío si la conexión se cerró).
        """
        data = await self.reader.read(max_bytes)
        if data:
            logger.debug("Recibidos %d bytes de %s", len(data), self.address)
        return data

    def close(self) -> None:
        """Cierra la conexión con el cliente."""
        self.writer.close()

    async def wait_closed(self) -> None:
        """Espera a que la conexión se cierre completamente."""
        await self.writer.wait_closed()
