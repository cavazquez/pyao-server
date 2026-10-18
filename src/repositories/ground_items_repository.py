"""Suelo persistido con identidades estables y mutaciones confirmadas por operación."""

import json
from typing import TYPE_CHECKING, Any, cast

from src.utils.durability import require_durable
from src.utils.gold_atomic import operation_id as new_operation_id
from src.utils.ground_state import GROUND_TTL_SECONDS, GroundItem, GroundState, stack_identity
from src.utils.redis_config import RedisKeys
from src.utils.resource_transaction import Decision, Resource, Snapshot, transact

if TYPE_CHECKING:
    from collections.abc import Callable

    from src.utils.redis_client import RedisClient


class GroundItemsRepository:
    """Lee el formato legado y confirma cada cambio sin snapshots ciegos en segundo plano."""

    GROUND_ITEMS_TTL = GROUND_TTL_SECONDS

    def __init__(self, redis_client: RedisClient) -> None:
        """Conserva el cliente efectivo."""
        self.redis_client = redis_client
        self.redis = redis_client

    async def save_ground_items(
        self, map_id: int, items: dict[tuple[int, int], list[GroundItem]]
    ) -> None:
        """Reemplaza un mapa únicamente para carga/mantenimiento sin sesiones activas.

        Raises:
            RuntimeError: Si existe una sesión que puede estar modificando el mundo.
        """
        async for _key in self.redis_client.redis.scan_iter(match="session:*:owner"):
            msg = "El reemplazo completo del suelo requiere el servidor sin sesiones activas"
            raise RuntimeError(msg)
        raw = json.dumps({f"{x},{y}": values for (x, y), values in items.items()})
        state = GroundState(map_id, raw)
        key = RedisKeys.ground_items(map_id)
        if items:
            await self.redis_client.set(key, state.encode(), ex=self.GROUND_ITEMS_TTL)
        else:
            await self.redis_client.delete(key)

    async def load_ground_items(self, map_id: int) -> dict[tuple[int, int], list[GroundItem]]:
        """Deriva IDs legacy deterministas sin reescribir datos ni esconder fallas de Redis.

        Returns:
            Stacks con identidad g1, conservando cantidad y metadatos.
        """
        raw = await self.redis_client.get(RedisKeys.ground_items(map_id))
        return GroundState(map_id, raw).positions()

    async def _mutate(
        self,
        map_id: int,
        identity: str,
        request: dict[str, Any],
        change: Callable[[GroundState], dict[str, Any]],
    ) -> dict[str, Any]:
        """Confirma suelo y recibo en un EXEC y exige AOF.

        Returns:
            Resultado confirmado, incluido un rechazo sin modificar el suelo.
        """
        key = RedisKeys.ground_items(map_id)

        def decide(snapshot: Snapshot) -> Decision:
            try:
                state = GroundState(map_id, cast("str | None", snapshot[key]))
                result = change(state)
            except (ValueError, TypeError) as error:
                return Decision({"applied": False, "error": str(error)}, {})
            return Decision(result, {key: state.encode()} if result["applied"] else {})

        redis = self.redis_client.redis
        await require_durable(redis)
        result = await transact(
            redis, (Resource(key, "string", self.GROUND_ITEMS_TTL),), identity, request, decide
        )
        await require_durable(redis)
        return result

    async def add_ground_item(
        self, map_id: int, x: int, y: int, item: GroundItem, *, operation_id: str | None = None
    ) -> dict[str, Any]:
        """Agrega un stack completo, identificado y recuperable ante un ACK incierto.

        Returns:
            Resultado confirmado de la creación o rechazo por capacidad.
        """
        identity = operation_id or new_operation_id()
        identified = {**item, "stack_id": stack_identity(identity)}

        def add(state: GroundState) -> dict[str, Any]:
            state.append(x, y, identified)
            return {"applied": True, "item": identified}

        return await self._mutate(
            map_id, identity, {"action": "spawn", "x": x, "y": y, "item": identified}, add
        )

    async def remove_ground_item(
        self, map_id: int, x: int, y: int, item_index: int = 0, *, operation_id: str | None = None
    ) -> GroundItem | None:
        """Remueve sólo un stack observado; no se usa para acreditar inventarios.

        Returns:
            Stack retirado o None si no está disponible.
        """
        selected: str | None = None

        def remove(state: GroundState) -> dict[str, Any]:
            nonlocal selected
            tile = state.tile(x, y)
            if selected is None:
                selected = str(tile[item_index]["stack_id"]) if 0 <= item_index < len(tile) else ""
            item = next((row for row in tile if row["stack_id"] == selected), None)
            if item is None:
                return {"applied": False}
            tile.remove(item)
            return {"applied": True, "item": item}

        result = await self._mutate(
            map_id,
            operation_id or new_operation_id(),
            {"action": "remove", "x": x, "y": y, "index": item_index},
            remove,
        )
        return cast("GroundItem", result["item"]) if result["applied"] else None

    async def clear_ground_items(self, map_id: int) -> int:
        """Limpia el mapa en una mutación identificada de mantenimiento.

        Returns:
            Cantidad de stacks retirados.
        """

        def clear(state: GroundState) -> dict[str, Any]:
            count = sum(len(items) for items in state.tiles.values())
            state.tiles.clear()
            return {"applied": True, "count": count}

        result = await self._mutate(map_id, new_operation_id(), {"action": "clear"}, clear)
        return int(result.get("count", 0))
