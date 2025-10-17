"""Repositorio para gestionar ground items (items en el suelo) en Redis."""

import json
import logging
from typing import TYPE_CHECKING

from src.redis_config import RedisKeys

if TYPE_CHECKING:
    from src.redis_client import RedisClient

logger = logging.getLogger(__name__)


class GroundItemsRepository:
    """Gestiona la persistencia de ground items en Redis."""

    GROUND_ITEMS_TTL = 3600  # TTL de 1 hora para items en el suelo

    def __init__(self, redis_client: RedisClient) -> None:
        """Inicializa el repositorio.

        Args:
            redis_client: Cliente de Redis.
        """
        self.redis_client = redis_client
        self.redis = redis_client.redis

    async def save_ground_items(
        self, map_id: int, items: dict[tuple[int, int], list[dict[str, int | str | None]]]
    ) -> None:
        """Guarda los ground items de un mapa en Redis.

        Args:
            map_id: ID del mapa.
            items: Diccionario {(x, y): [items]} con los items del mapa.
        """
        try:
            key = RedisKeys.ground_items(map_id)

            # Convertir a formato serializable
            serializable_items = {}
            for (x, y), item_list in items.items():
                coord_key = f"{x},{y}"
                serializable_items[coord_key] = item_list

            # Guardar en Redis como JSON
            if serializable_items:
                await self.redis.set(key, json.dumps(serializable_items), ex=self.GROUND_ITEMS_TTL)
                logger.debug(
                    "Guardados %d tiles con items en mapa %d", len(serializable_items), map_id
                )
            else:
                # Si no hay items, eliminar la clave
                await self.redis.delete(key)

        except Exception:
            logger.exception("Error al guardar ground items del mapa %d", map_id)

    async def load_ground_items(
        self, map_id: int
    ) -> dict[tuple[int, int], list[dict[str, int | str | None]]]:
        """Carga los ground items de un mapa desde Redis.

        Args:
            map_id: ID del mapa.

        Returns:
            Diccionario {(x, y): [items]} con los items del mapa.
        """
        try:
            key = RedisKeys.ground_items(map_id)
            data = await self.redis.get(key)

            if not data:
                return {}

            # Deserializar
            serializable_items = json.loads(data)

            # Convertir de vuelta a tuplas
            items: dict[tuple[int, int], list[dict[str, int | str | None]]] = {}
            for coord_key, item_list in serializable_items.items():
                x_str, y_str = coord_key.split(",")
                x, y = int(x_str), int(y_str)
                items[x, y] = item_list

            logger.debug("Cargados %d tiles con items del mapa %d", len(items), map_id)
            return items  # noqa: TRY300
        except Exception:
            logger.exception("Error al cargar ground items del mapa %d", map_id)
            return {}

    async def add_ground_item(
        self, map_id: int, x: int, y: int, item: dict[str, int | str | None]
    ) -> None:
        """Agrega un item al suelo y lo persiste en Redis.

        Args:
            map_id: ID del mapa.
            x: Posición X.
            y: Posición Y.
            item: Item a agregar.
        """
        try:
            # Cargar items actuales
            items = await self.load_ground_items(map_id)

            # Agregar nuevo item
            coord = (x, y)
            if coord not in items:
                items[coord] = []
            items[coord].append(item)

            # Guardar de vuelta
            await self.save_ground_items(map_id, items)

        except Exception:
            logger.exception("Error al agregar ground item en mapa %d pos (%d,%d)", map_id, x, y)

    async def remove_ground_item(
        self, map_id: int, x: int, y: int, item_index: int = 0
    ) -> dict[str, int | str | None] | None:
        """Remueve un item del suelo y actualiza Redis.

        Args:
            map_id: ID del mapa.
            x: Posición X.
            y: Posición Y.
            item_index: Índice del item en la lista.

        Returns:
            Item removido o None si no existe.
        """
        try:
            # Cargar items actuales
            items = await self.load_ground_items(map_id)

            coord = (x, y)
            if coord not in items or item_index >= len(items[coord]):
                return None

            # Remover item
            item = items[coord].pop(item_index)

            # Limpiar si no quedan items
            if not items[coord]:
                del items[coord]

            # Guardar de vuelta
            await self.save_ground_items(map_id, items)

            return item  # noqa: TRY300

        except Exception:
            logger.exception("Error al remover ground item en mapa %d pos (%d,%d)", map_id, x, y)
            return None

    async def clear_ground_items(self, map_id: int) -> int:
        """Limpia todos los items de un mapa.

        Args:
            map_id: ID del mapa.

        Returns:
            Cantidad de tiles limpiados.
        """
        try:
            items = await self.load_ground_items(map_id)
            count = len(items)

            # Eliminar de Redis
            key = RedisKeys.ground_items(map_id)
            await self.redis.delete(key)

            if count > 0:
                logger.info("Limpiados %d tiles con items del mapa %d", count, map_id)

            return count  # noqa: TRY300

        except Exception:
            logger.exception("Error al limpiar ground items del mapa %d", map_id)
            return 0
