"""Manejo de conexiones de cliente."""

import asyncio
import logging

logger = logging.getLogger(__name__)


class ClientConnection:
    """Encapsula la conexión con un cliente y provee métodos para comunicación."""

    def __init__(self, writer: asyncio.StreamWriter) -> None:
        """Inicializa la conexión del cliente.

        Args:
            writer: Stream para enviar datos al cliente.
        """
        self.writer = writer
        self.address = writer.get_extra_info("peername")

    async def send(self, data: bytes) -> None:
        """Envía datos al cliente.

        Args:
            data: Bytes a enviar al cliente.
        """
        self.writer.write(data)
        await self.writer.drain()
        logger.debug("Enviados %d bytes a %s", len(data), self.address)

    def close(self) -> None:
        """Cierra la conexión con el cliente."""
        self.writer.close()

    async def wait_closed(self) -> None:
        """Espera a que la conexión se cierre completamente."""
        await self.writer.wait_closed()
