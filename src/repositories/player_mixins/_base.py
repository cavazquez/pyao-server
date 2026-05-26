"""Player repository mixins."""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.utils.redis_client import RedisClient
else:
    RedisClient = object

logger = logging.getLogger(__name__)


class PlayerRepositoryBase:
    """Redis helpers shared by player repository mixins."""

    redis: RedisClient

    # ── Redis hash helpers ──────────────────────────────────────────────

    async def _hget_float(self, key: str, field: str, default: float = 0.0) -> float:
        """Lee un campo float de un hash Redis.

        Returns:
            Valor float del campo o default si no existe / es inválido.
        """
        result = await self.redis.hget(key, field)
        if not result:
            return default
        try:
            return float(result)
        except ValueError, TypeError:
            return default

    async def _hget_int(self, key: str, field: str, default: int = 0) -> int:
        """Lee un campo int de un hash Redis.

        Returns:
            Valor int del campo o default si no existe / es inválido.
        """
        result = await self.redis.hget(key, field)
        if not result:
            return default
        try:
            return int(result)
        except ValueError, TypeError:
            return default

    async def _hget_bool(self, key: str, field: str) -> bool:
        """Lee un campo booleano (1/0) de un hash Redis.

        Returns:
            True si el campo es "1", False en caso contrario.
        """
        result = await self.redis.hget(key, field)
        return result in {b"1", "1", 1} if result else False

    async def _hset_field(self, key: str, field: str, value: str | float) -> None:
        """Escribe un campo en un hash Redis."""
        await self.redis.hset_field(key, field, str(value))
