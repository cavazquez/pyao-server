"""Índice de ground items por mapa con persistencia opcional."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.repositories.ground_items_repository import GroundItemsRepository

logger = logging.getLogger(__name__)


class GroundItemIndex:
    """Gestiona items en el suelo agrupados por mapa y posición."""

    def __init__(
        self,
        max_items_per_tile: int,
        ground_items_repo: GroundItemsRepository | None = None,
    ) -> None:
        """Inicializa el índice.

        Args:
            max_items_per_tile: Límite de items por tile.
            ground_items_repo: Repo opcional para persistencia en Redis.
        """
        self.max_items_per_tile = max_items_per_tile
        self.ground_items_repo = ground_items_repo
        self._ground_items: dict[tuple[int, int, int], list[dict[str, int | str | None]]] = {}

    @property
    def ground_items(self) -> dict[tuple[int, int, int], list[dict[str, int | str | None]]]:
        """Storage interno (compatibilidad con MapManager)."""
        return self._ground_items

    def add_ground_item(
        self, map_id: int, x: int, y: int, item: dict[str, int | str | None]
    ) -> None:
        """Agrega un item al suelo en una posición específica."""
        key = (map_id, x, y)
        if key not in self._ground_items:
            self._ground_items[key] = []

        if len(self._ground_items[key]) >= self.max_items_per_tile:
            logger.warning(
                "Tile (%d, %d) en mapa %d tiene %d items, no se puede agregar más",
                x,
                y,
                map_id,
                self.max_items_per_tile,
            )
            return

        self._ground_items[key].append(item)
        logger.debug(
            "Item agregado al suelo: mapa=%d pos=(%d,%d) item_id=%s cantidad=%s",
            map_id,
            x,
            y,
            item.get("item_id"),
            item.get("quantity"),
        )

        if self.ground_items_repo:
            task = asyncio.create_task(self.persist_ground_items(map_id))
            task.add_done_callback(lambda t: t.exception() if not t.cancelled() else None)

    def get_ground_items(self, map_id: int, x: int, y: int) -> list[dict[str, int | str | None]]:
        """Obtiene todos los items en un tile específico.

        Returns:
            list[dict[str, int | str | None]]: Items en el tile (o lista vacía).
        """
        return self._ground_items.get((map_id, x, y), [])

    def remove_ground_item(
        self, map_id: int, x: int, y: int, item_index: int = 0
    ) -> dict[str, int | str | None] | None:
        """Remueve un item del suelo.

        Returns:
            dict[str, int | str | None] | None: Item removido o None si no existe.
        """
        key = (map_id, x, y)
        if key not in self._ground_items:
            return None

        items = self._ground_items[key]
        if item_index >= len(items):
            logger.warning(
                "Intento de remover item_index=%d pero solo hay %d items en (%d,%d)",
                item_index,
                len(items),
                x,
                y,
            )
            return None

        item = items.pop(item_index)
        if not items:
            del self._ground_items[key]

        logger.debug(
            "Item removido del suelo: mapa=%d pos=(%d,%d) item_id=%s",
            map_id,
            x,
            y,
            item.get("item_id"),
        )

        if self.ground_items_repo:
            task = asyncio.create_task(self.persist_ground_items(map_id))
            task.add_done_callback(lambda t: t.exception() if not t.cancelled() else None)

        return item

    def clear_ground_items(self, map_id: int) -> int:
        """Limpia todos los items de un mapa.

        Returns:
            int: Cantidad de items removidos.
        """
        keys_to_remove = [key for key in self._ground_items if key[0] == map_id]
        total_items = sum(len(self._ground_items[key]) for key in keys_to_remove)

        for key in keys_to_remove:
            del self._ground_items[key]

        if total_items > 0:
            logger.info("Limpiados %d items del mapa %d", total_items, map_id)

        return total_items

    def get_ground_items_count(self, map_id: int) -> int:
        """Obtiene la cantidad total de items en el suelo de un mapa.

        Returns:
            int: Total de items.
        """
        return sum(len(items) for key, items in self._ground_items.items() if key[0] == map_id)

    async def persist_ground_items(self, map_id: int) -> None:
        """Persiste los ground items de un mapa en Redis."""
        if not self.ground_items_repo:
            return

        map_items: dict[tuple[int, int], list[dict[str, int | str | None]]] = {}
        for (item_map_id, x, y), items in self._ground_items.items():
            if item_map_id == map_id:
                map_items[x, y] = items

        await self.ground_items_repo.save_ground_items(map_id, map_items)

    async def load_ground_items(self, map_id: int) -> None:
        """Carga los ground items de un mapa desde Redis."""
        if not self.ground_items_repo:
            return

        map_items = await self.ground_items_repo.load_ground_items(map_id)
        for (x, y), items in map_items.items():
            self._ground_items[map_id, x, y] = items

        if map_items:
            total_items = sum(len(items) for items in map_items.values())
            logger.info("Cargados %d items del mapa %d desde Redis", total_items, map_id)
