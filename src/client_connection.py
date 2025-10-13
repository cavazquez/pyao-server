"""Manejo de conexiones de cliente."""

import asyncio
import logging

logger = logging.getLogger(__name__)

# Constante para el límite de bytes a mostrar en logs
MAX_LOG_BYTES = 32


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
        hex_data = " ".join(f"{byte:02X}" for byte in data[:MAX_LOG_BYTES])
        logger.info(
            "Enviados %d bytes a %s: %s%s",
            len(data),
            self.address,
            hex_data,
            "..." if len(data) > MAX_LOG_BYTES else "",
        )

    def close(self) -> None:
        """Cierra la conexión con el cliente."""
        self.writer.close()

    async def wait_closed(self) -> None:
        """Espera a que la conexión se cierre completamente."""
        await self.writer.wait_closed()
