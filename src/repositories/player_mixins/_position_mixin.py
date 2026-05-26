"""Player repository mixins."""

import logging
from typing import TYPE_CHECKING

from src.utils.redis_config import RedisKeys

if TYPE_CHECKING:
    from src.utils.redis_client import RedisClient
else:
    RedisClient = object


logger = logging.getLogger(__name__)


class PlayerPositionMixin:
    """Position and heading operations."""

    async def get_position(self, user_id: int) -> dict[str, int] | None:
        """Obtiene la posición del jugador.

        Args:
            user_id: ID del usuario.

        Returns:
            Diccionario con x, y, map, heading o None si no existe.
        """
        key = RedisKeys.player_position(user_id)
        result: dict[str, str] = await self.redis.hgetall(key)

        if not result:
            return None

        return {
            "x": int(result.get("x", 50)),
            "y": int(result.get("y", 50)),
            "map": int(result.get("map", 1)),
            "heading": int(result.get("heading", 3)),  # 3 = Sur por defecto
        }

    async def set_position(
        self, user_id: int, x: int, y: int, map_number: int, heading: int | None = None
    ) -> None:
        """Guarda la posición del jugador.

        Args:
            user_id: ID del usuario.
            x: Posición X.
            y: Posición Y.
            map_number: Número del mapa.
            heading: Dirección (1=Norte, 2=Este, 3=Sur, 4=Oeste), opcional.
        """
        key = RedisKeys.player_position(user_id)
        position_data = {
            "x": str(x),
            "y": str(y),
            "map": str(map_number),
        }
        if heading is not None:
            position_data["heading"] = str(heading)
        await self.redis.hset(key, mapping=position_data)
        logger.debug(
            "Posición guardada para user_id %d: (%d, %d) en mapa %d", user_id, x, y, map_number
        )

    async def set_heading(self, user_id: int, heading: int) -> None:
        """Actualiza solo la dirección del jugador.

        Args:
            user_id: ID del usuario.
            heading: Dirección (1=Norte, 2=Este, 3=Sur, 4=Oeste).
        """
        key = RedisKeys.player_position(user_id)
        await self.redis.hset(key, "heading", str(heading))
        logger.debug("Dirección actualizada para user_id %d: heading=%d", user_id, heading)
