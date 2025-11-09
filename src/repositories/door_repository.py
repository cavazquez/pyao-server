"""Repositorio para gestionar el estado de las puertas en Redis."""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.utils.redis_client import RedisClient

logger = logging.getLogger(__name__)


class DoorRepository:
    """Repositorio para gestionar el estado de puertas en mapas."""

    def __init__(self, redis: RedisClient | None = None) -> None:
        """Inicializa el repositorio.

        Args:
            redis: Cliente Redis.
        """
        self.redis = redis

    @staticmethod
    def _get_door_key(map_id: int, x: int, y: int) -> str:
        """Genera la key de Redis para una puerta.

        Args:
            map_id: ID del mapa.
            x: Coordenada X.
            y: Coordenada Y.

        Returns:
            Key de Redis.
        """
        return f"door:{map_id}:{x}:{y}"

    async def get_door_state(self, map_id: int, x: int, y: int) -> tuple[int, bool] | None:
        """Obtiene el estado de una puerta.

        Args:
            map_id: ID del mapa.
            x: Coordenada X.
            y: Coordenada Y.

        Returns:
            Tupla (item_id, is_open) o None si no existe estado guardado.
        """
        if not self.redis or not self.redis.redis:
            return None

        key = self._get_door_key(map_id, x, y)

        try:
            value = await self.redis.redis.get(key)
            if not value:
                return None

            # Redis puede devolver bytes o str dependiendo de la configuración
            value_str = value.decode("utf-8") if isinstance(value, bytes) else str(value)

            parts = value_str.split(":")
            expected_parts = 2
            if len(parts) != expected_parts:
                return None

            item_id = int(parts[0])
            is_open = parts[1] == "1"
        except Exception:
            logger.exception("Error obteniendo estado de puerta en (%d, %d, %d)", map_id, x, y)
            return None
        else:
            return item_id, is_open

    async def set_door_state(
        self, map_id: int, x: int, y: int, item_id: int, is_open: bool
    ) -> bool:
        """Guarda el estado de una puerta.

        Args:
            map_id: ID del mapa.
            x: Coordenada X.
            y: Coordenada Y.
            item_id: ID del item de la puerta.
            is_open: True si está abierta, False si está cerrada.

        Returns:
            True si se guardó correctamente.
        """
        if not self.redis or not self.redis.redis:
            return False

        key = self._get_door_key(map_id, x, y)
        value = f"{item_id}:{'1' if is_open else '0'}"

        try:
            await self.redis.redis.set(key, value)
        except Exception:
            logger.exception("Error guardando estado de puerta en (%d, %d, %d)", map_id, x, y)
            return False
        else:
            return True

    async def delete_door_state(self, map_id: int, x: int, y: int) -> bool:
        """Elimina el estado de una puerta (vuelve al estado por defecto).

        Args:
            map_id: ID del mapa.
            x: Coordenada X.
            y: Coordenada Y.

        Returns:
            True si se eliminó correctamente.
        """
        if not self.redis or not self.redis.redis:
            return False

        key = self._get_door_key(map_id, x, y)

        try:
            await self.redis.redis.delete(key)
        except Exception:
            logger.exception("Error eliminando estado de puerta en (%d, %d, %d)", map_id, x, y)
            return False
        else:
            return True
