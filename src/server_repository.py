"""Repositorio para configuraciones y datos del servidor."""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.redis_client import RedisClient

logger = logging.getLogger(__name__)


class ServerRepository:
    """Repositorio para gestionar configuraciones del servidor."""

    def __init__(self, redis_client: RedisClient) -> None:
        """Inicializa el repositorio del servidor.

        Args:
            redis_client: Cliente de Redis.
        """
        self.redis_client = redis_client

    async def get_motd(self) -> str:
        """Obtiene el Mensaje del Día desde Redis.

        Returns:
            El mensaje del día o un mensaje por defecto si no existe.
        """
        value = await self.redis_client.redis.get("server:motd")
        if value is None:
            return "Bienvenido a Argentum Online!\nServidor en desarrollo."
        return str(value)

    async def set_motd(self, message: str) -> None:
        """Establece el Mensaje del Día en Redis.

        Args:
            message: El nuevo mensaje del día.
        """
        await self.redis_client.redis.set("server:motd", message)
        logger.info("MOTD actualizado: %s", message[:50])

    async def get_uptime_start(self) -> int | None:
        """Obtiene el timestamp de inicio del servidor.

        Returns:
            Timestamp de inicio o None si no existe.
        """
        value = await self.redis_client.redis.get("server:uptime:start")
        if value is None:
            return None
        return int(value)

    async def set_uptime_start(self, timestamp: int) -> None:
        """Establece el timestamp de inicio del servidor.

        Args:
            timestamp: Timestamp de inicio.
        """
        await self.redis_client.redis.set("server:uptime:start", str(timestamp))
        logger.info("Timestamp de inicio del servidor establecido: %d", timestamp)
