"""Índice de ground items por mapa con persistencia opcional."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from src.models.items_catalog import ITEMS_CATALOG
from src.utils.gold_atomic import RECEIPT_TTL_SECONDS
from src.utils.gold_atomic import operation_id as new_operation_id
from src.utils.ground_state import GroundItem, GroundState, stack_identity
from src.utils.redis_config import RedisKeys

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from redis.asyncio import Redis

    from src.repositories.ground_items_repository import GroundItemsRepository
    from src.services.multiplayer_broadcast_service import MultiplayerBroadcastService

logger = logging.getLogger(__name__)
SNAPSHOT_SEND_BATCH = 32


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
        self._published: dict[str, float] = {}
        self._locks: dict[int, asyncio.Lock] = {}
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
        self._require_memory_mode()
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

    def get_ground_items(self, map_id: int, x: int, y: int) -> list[dict[str, int | str | None]]:
        """Obtiene todos los items en un tile específico.

        Returns:
            list[dict[str, int | str | None]]: Items en el tile (o lista vacía).
        """
        return self._ground_items.get((map_id, x, y), [])

    @staticmethod
    def _graphic_for(item: dict[str, int | str | None]) -> int:
        graphic = item.get("grh_index")
        if not isinstance(graphic, int):
            definition = ITEMS_CATALOG.get(int(item.get("item_id") or 0))
            graphic = definition.graphic_id if definition else 0
        return graphic

    async def send_snapshot(
        self, map_id: int, send_object: Callable[[int, int, int], Awaitable[None]]
    ) -> int:
        """Encola el suelo visible antes de permitir nuevas cargas/commits/notificaciones.

        Returns:
            Número de posiciones visibles enviadas.
        """
        async with self._locks.setdefault(map_id, asyncio.Lock()):
            entries = [
                (x, y, self._graphic_for(items[0]))
                for (current_map, x, y), items in self._ground_items.items()
                if current_map == map_id and items
            ]
            sent = 0
            for x, y, graphic in entries:
                if graphic > 0:
                    await send_object(x, y, graphic)
                    sent += 1
                    if sent % SNAPSHOT_SEND_BATCH == 0:
                        await asyncio.sleep(0)
            return sent

    def remove_ground_item(
        self, map_id: int, x: int, y: int, item_index: int = 0
    ) -> dict[str, int | str | None] | None:
        """Remueve un item del suelo.

        Returns:
            dict[str, int | str | None] | None: Item removido o None si no existe.
        """
        self._require_memory_mode()
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

        return item

    def clear_ground_items(self, map_id: int) -> int:
        """Limpia todos los items de un mapa.

        Returns:
            int: Cantidad de items removidos.
        """
        self._require_memory_mode()
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

    def _require_memory_mode(self) -> None:
        """Impide reintroducir snapshots ciegos desde la API síncrona de tests.

        Raises:
            RuntimeError: Si se intenta mutar suelo persistido sin esperar el commit.
        """
        if self.ground_items_repo is not None:
            msg = "El suelo persistido requiere la API de commit esperable"
            raise RuntimeError(msg)

    async def persist_ground_items(self, _map_id: int) -> None:
        """La API antigua sólo se admite en el modo puramente en memoria."""
        self._require_memory_mode()

    def _replace_map(self, map_id: int, positions: dict[tuple[int, int], list[GroundItem]]) -> None:
        for key in [key for key in self._ground_items if key[0] == map_id]:
            del self._ground_items[key]
        for (x, y), values in positions.items():
            self._ground_items[map_id, x, y] = [item.copy() for item in values]

    async def load_ground_items(self, map_id: int) -> None:
        """Carga el mapa en la misma exclusión que sus commits y notificaciones."""
        if self.ground_items_repo is None:
            return
        async with self._locks.setdefault(map_id, asyncio.Lock()):
            self._replace_map(map_id, await self.ground_items_repo.load_ground_items(map_id))

    async def _publish(
        self, map_id: int, x: int, y: int, broadcast: MultiplayerBroadcastService | None
    ) -> None:
        if broadcast is None:
            return
        await broadcast.broadcast_object_delete(map_id, x, y)
        tile = self.get_ground_items(map_id, x, y)
        if not tile:
            return
        graphic = self._graphic_for(tile[0])
        if graphic > 0:
            await broadcast.broadcast_object_create(map_id=map_id, x=x, y=y, grh_index=graphic)

    async def run_committed(
        self,
        map_id: int,
        x: int,
        y: int,
        redis: Redis,
        operation: Callable[[], Awaitable[dict[str, Any]]],
        broadcast: MultiplayerBroadcastService | None,
        identity: str | None = None,
    ) -> dict[str, Any]:
        """Ordena commit, caché y notificación; un replay nunca repone una caché vieja.

        Returns:
            Resultado confirmado de la operación solicitada.
        """
        async with self._locks.setdefault(map_id, asyncio.Lock()):
            result = await operation()
            raw = await redis.get(RedisKeys.ground_items(map_id))
            self._replace_map(map_id, GroundState(map_id, raw).positions())
            now = asyncio.get_running_loop().time()
            self._published = {
                key: expiry for key, expiry in self._published.items() if expiry > now
            }
            if identity is None or identity not in self._published:
                await self._publish(map_id, x, y, broadcast)
                if identity is not None:
                    self._published[identity] = now + RECEIPT_TTL_SECONDS
            return result

    async def add_committed(
        self,
        map_id: int,
        x: int,
        y: int,
        item: GroundItem,
        broadcast: MultiplayerBroadcastService | None,
        identity: str | None = None,
    ) -> bool:
        """Agrega y publica sólo después del commit, respetando capacidad e identidad.

        Returns:
            Si el stack fue persistido; el modo sin repositorio es sólo de test en memoria.
        """
        identity = identity or new_operation_id()
        if self.ground_items_repo is None:
            async with self._locks.setdefault(map_id, asyncio.Lock()):
                if len(self.get_ground_items(map_id, x, y)) >= self.max_items_per_tile:
                    return False
                self.add_ground_item(map_id, x, y, {**item, "stack_id": stack_identity(identity)})
                await self._publish(map_id, x, y, broadcast)
                return True
        repository = self.ground_items_repo
        result = await self.run_committed(
            map_id,
            x,
            y,
            repository.redis_client.redis,
            lambda: repository.add_ground_item(map_id, x, y, item, operation_id=identity),
            broadcast,
            identity,
        )
        return bool(result["applied"])
