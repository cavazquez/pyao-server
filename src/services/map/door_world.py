"""Puertas dinámicas compartidas por colisiones, snapshots y observadores."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from src.utils.durability import require_durable
from src.utils.gold_atomic import operation_id
from src.utils.resource_transaction import Decision, Resource, Snapshot, transact

if TYPE_CHECKING:
    from src.game.map_manager import MapManager
    from src.messaging.message_sender import MessageSender
    from src.repositories.door_repository import DoorRepository
    from src.services.map.door_service import DoorInfo, DoorService
    from src.services.map.map_resources_service import MapResourcesService

logger = logging.getLogger(__name__)
WOODEN_CLOSED_GRAPHIC = 5593
WOODEN_CLOSED_ITEM = 8
type Cell = tuple[int, int]


class DoorWorld:
    """Restaura Redis antes del spawn y serializa cada snapshot con los cambios."""

    def __init__(
        self,
        maps: MapManager,
        terrain: MapResourcesService,
        repository: DoorRepository,
        catalog: DoorService,
    ) -> None:
        """Conserva definiciones estáticas y estado de las pocas puertas del mundo."""
        self.maps, self.terrain, self.repository, self.catalog = maps, terrain, repository, catalog
        self.states: dict[int, dict[Cell, DoorInfo]] = {}
        self.defaults: dict[int, dict[Cell, DoorInfo]] = {}
        self.locks: dict[int, asyncio.Lock] = {}
        self.pending: dict[int, set[Cell]] = {}

    def _apply(self, mid: int, cell: Cell, info: DoorInfo) -> None:
        x, y = cell
        self.maps.register_door_state(mid, x, y, closed=not info.is_open)
        row = self.terrain.resources.get(f"map_{mid}")
        if row is not None:
            row["blocked"].discard(cell)

    async def restore(self) -> None:
        """Lee estados sin sobrescribir Redis y publica la colisión antes de los NPCs.

        Raises:
            ValueError: Si una puerta persistida ya no existe en el catálogo o está sobre agua.
        """
        for key, definitions in self.terrain.doors.items():
            mid = int(key.removeprefix("map_"))
            for cell, graphic in definitions.items():
                initial = (
                    self.catalog.get_door_by_id(WOODEN_CLOSED_ITEM)
                    if graphic == WOODEN_CLOSED_GRAPHIC
                    else self.catalog.get_door_by_grh(graphic)
                )
                saved = await self.repository.get_door_state(mid, *cell)
                info = self.catalog.get_door_by_id(saved[0]) if saved else initial
                if info is None or initial is None or self.terrain.has_water(mid, *cell):
                    message = f"Puerta inválida en {mid}:{cell}"
                    raise ValueError(message)
                self.states.setdefault(mid, {})[cell] = info
                self.defaults.setdefault(mid, {})[cell] = initial
                self._apply(mid, cell, info)
            self.locks[mid] = asyncio.Lock()

    @staticmethod
    async def _send(sender: MessageSender, states: dict[Cell, DoorInfo]) -> None:
        for (x, y), info in sorted(states.items()):
            await sender.send_object_create(x, y, info.grh_index)
            await sender.send_block_position(x, y, blocked=not info.is_open)

    async def snapshot(self, mid: int, sender: MessageSender) -> int:
        """Envía gráfico y colisión coherentes antes del actor local.

        Returns:
            Cantidad de puertas publicadas.
        """
        if mid not in self.states:
            return 0
        async with self.locks[mid]:
            await self._reconcile(mid)
            await self._send(sender, self.states[mid])
        return len(self.states[mid])

    async def toggle(self, mid: int, x: int, y: int) -> dict[str, Any]:
        """Difiere la cancelación hasta resolver el commit y publicar su estado.

        Returns:
            Estado confirmado o rechazo sin escrituras.

        Raises:
            asyncio.CancelledError: Tras completar una operación cuya conexión se canceló.
        """
        task = asyncio.create_task(self._toggle(mid, x, y))
        cancelled = False
        while True:
            try:
                result = await asyncio.shield(task)
                break
            except asyncio.CancelledError:
                if task.cancelled():
                    raise
                cancelled = True
        if cancelled:
            raise asyncio.CancelledError
        return result

    async def _publish(self, mid: int, changed: dict[Cell, DoorInfo]) -> None:
        deliveries = await asyncio.gather(
            *(
                self._send(sender, changed)
                for sender in self.maps.get_all_message_senders_in_map(mid)
            ),
            return_exceptions=True,
        )
        for delivered in deliveries:
            if isinstance(delivered, Exception):
                logger.warning("Observador desconectado durante cambio de puerta: %s", delivered)

    async def _reconcile(self, mid: int) -> None:
        """Resuelve un resultado incierto antes de otro cambio o snapshot.

        Si Redis sigue caído, conserva la colisión cerrada y la marca pendiente.
        La siguiente operación consulta las mismas claves, sin volver a alternarlas.

        Raises:
            RuntimeError: Si falta Redis o el estado guardado no pertenece al catálogo.
        """
        cells = sorted(self.pending.get(mid, ()))
        if not cells:
            return
        if self.repository.redis is None:
            message = "Repositorio de puertas sin Redis"
            raise RuntimeError(message)
        values = await self.repository.redis.redis.mget(
            [self.repository.state_key(mid, *cell) for cell in cells]
        )
        changed = {}
        for cell, raw_value in zip(cells, values, strict=True):
            value = raw_value.decode() if isinstance(raw_value, bytes) else raw_value
            info = (
                self.defaults[mid][cell]
                if value is None
                else self.catalog.get_door_by_id(int(value.split(":")[0]))
            )
            if info is None:
                message = f"Puerta persistida inválida en {mid}:{cell}"
                raise RuntimeError(message)
            changed[cell] = info
        self.states[mid].update(changed)
        for cell, info in changed.items():
            self._apply(mid, cell, info)
        self.pending.pop(mid, None)
        await self._publish(mid, changed)

    async def _toggle(self, mid: int, x: int, y: int) -> dict[str, Any]:
        """Confirma las mitades juntas y publica el mismo resultado a todos.

        Returns:
            Estado confirmado o rechazo sin escrituras.

        Raises:
            RuntimeError: Si el repositorio no tiene conexión Redis.
        """
        if (x, y) not in self.states.get(mid, {}):
            return {"applied": False, "message": "La puerta no existe."}
        async with self.locks[mid]:
            await self._reconcile(mid)
            current = self.states[mid][x, y]
            family = (current.index_open, current.index_closed)
            cells = [
                (x, y),
                *(
                    (xx, y)
                    for xx in (x - 1, x + 1)
                    if (xx, y) in self.states[mid]
                    and (self.states[mid][xx, y].index_open, self.states[mid][xx, y].index_closed)
                    == family
                ),
            ]
            if any(self.maps.is_tile_occupied(mid, *cell) for cell in cells):
                return {"applied": False, "message": "La puerta está ocupada."}
            previous = {cell: self.states[mid][cell] for cell in cells}
            keys = {cell: self.repository.state_key(mid, *cell) for cell in cells}
            if self.repository.redis is None:
                message = "Repositorio de puertas sin Redis"
                raise RuntimeError(message)
            raw = self.repository.redis.redis
            await require_durable(raw)
            # Durabilidad puede suspender: comprobar de nuevo antes de cerrar
            # la colisión, sin otro await entre la reserva y esta decisión.
            if any(self.maps.is_tile_occupied(mid, *cell) for cell in cells):
                return {"applied": False, "message": "La puerta está ocupada."}
            # Cerrar temporalmente evita una llegada durante el await de Redis.
            for cell in cells:
                self.maps.block_tile(mid, *cell)
            self.pending[mid] = set(cells)

            def decide(snapshot: Snapshot) -> Decision:
                value = snapshot[keys[x, y]]
                item = (
                    self.catalog.get_door_by_id(int(value.split(":")[0]))
                    if isinstance(value, str)
                    else current
                )
                if item is None or item.requires_key:
                    return Decision(
                        {"applied": False, "message": "La puerta está cerrada con llave."}, {}
                    )
                new_id, is_open = self.catalog.toggle_door(item)
                return Decision(
                    {"applied": True, "item_id": new_id, "is_open": is_open},
                    {key: f"{new_id}:{int(is_open)}" for key in keys.values()},
                )

            try:
                result = await transact(
                    raw,
                    tuple(Resource(key, "string") for key in keys.values()),
                    operation_id(),
                    {"toggle_door": [mid, x, y]},
                    decide,
                )
                if not result["applied"]:
                    for cell, info in previous.items():
                        self._apply(mid, cell, info)
                    self.pending.pop(mid, None)
                    return result
                confirmed = self.catalog.get_door_by_id(int(result["item_id"]))
                assert confirmed is not None  # ruff: ignore[assert] - ID selected from this catalogue
                changed = dict.fromkeys(cells, confirmed)
                self.states[mid].update(changed)
                for cell in cells:
                    self._apply(mid, cell, confirmed)
                await require_durable(raw)
            except Exception:
                try:
                    await self._reconcile(mid)
                except Exception:
                    logger.exception("Puertas pendientes de reconciliar en mapa %d", mid)
                raise
            self.pending.pop(mid, None)
            await self._publish(mid, changed)
            return {**result, "type": "door", "map_id": mid, "x": x, "y": y}
