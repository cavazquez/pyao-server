"""Manejo de conexiones de cliente."""

import asyncio
import logging

from src.security.auth_limits import AuthLimiter, ConnectionAttempts

logger = logging.getLogger(__name__)


class ClientConnection:
    """Encapsula la conexión con un cliente y provee métodos para comunicación."""

    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        """Inicializa la conexión del cliente.

        Args:
            reader: Stream para leer datos del cliente.
            writer: Stream para enviar datos al cliente.
        """
        self.auth_limiter: AuthLimiter | None = None
        self.auth_attempts = ConnectionAttempts()
        self.is_authenticated = False
        self.reader = reader
        self.writer = writer
        self.address = writer.get_extra_info("peername")
        self.is_ssl_enabled = writer.get_extra_info("ssl_object") is not None

    def allow_authentication(self, username: str) -> bool:
        """Consume el presupuesto de autenticación antes de ejecutar Argon2.

        Returns:
            True si el intento está permitido por conexión/IP/cuenta.
        """
        if self.is_authenticated:
            return False
        if self.auth_limiter is None:
            # Sólo conexiones de prueba/uso aislado carecen del limitador del servidor.
            return True
        ip = str(self.address[0]) if isinstance(self.address, tuple) else str(self.address)
        return self.auth_limiter.allow(ip, username, self.auth_attempts)

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
