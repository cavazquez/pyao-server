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

    # Configuración de efectos del juego
    async def get_effect_config_int(self, key: str, default: int) -> int:
        """Obtiene un valor de configuración de efecto como entero.

        Args:
            key: Clave de configuración.
            default: Valor por defecto si no existe.

        Returns:
            Valor de configuración como entero.
        """
        value = await self.redis_client.redis.get(key)
        if value is None:
            return default
        try:
            return int(value)
        except ValueError:
            logger.warning("Valor inválido para %s: %s, usando default %d", key, value, default)
            return default

    async def get_effect_config_float(self, key: str, default: float) -> float:
        """Obtiene un valor de configuración de efecto como float.

        Args:
            key: Clave de configuración.
            default: Valor por defecto si no existe.

        Returns:
            Valor de configuración como float.
        """
        value = await self.redis_client.redis.get(key)
        if value is None:
            return default
        try:
            return float(value)
        except ValueError:
            logger.warning("Valor inválido para %s: %s, usando default %.2f", key, value, default)
            return default

    async def get_effect_config_bool(self, key: str, *, default: bool) -> bool:
        """Obtiene un valor de configuración de efecto como booleano.

        Args:
            key: Clave de configuración.
            default: Valor por defecto si no existe.

        Returns:
            Valor de configuración como booleano (1=True, 0=False).
        """
        value = await self.redis_client.redis.get(key)
        if value is None:
            return default
        return bool(value == "1")

    # Configuración de dados
    async def get_dice_min_value(self) -> int:
        """Obtiene el valor mínimo para tirada de dados.

        Returns:
            Valor mínimo (default: 6).
        """
        return await self.get_effect_config_int("server:dice:min_value", 6)

    async def get_dice_max_value(self) -> int:
        """Obtiene el valor máximo para tirada de dados.

        Returns:
            Valor máximo (default: 18).
        """
        return await self.get_effect_config_int("server:dice:max_value", 18)

    async def set_dice_min_value(self, value: int) -> None:
        """Establece el valor mínimo para tirada de dados.

        Args:
            value: Nuevo valor mínimo.
        """
        await self.redis_client.redis.set("server:dice:min_value", str(value))
        logger.info("Valor mínimo de dados establecido: %d", value)

    async def set_dice_max_value(self, value: int) -> None:
        """Establece el valor máximo para tirada de dados.

        Args:
            value: Nuevo valor máximo.
        """
        await self.redis_client.redis.set("server:dice:max_value", str(value))
        logger.info("Valor máximo de dados establecido: %d", value)
