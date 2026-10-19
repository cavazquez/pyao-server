"""Devaluación durable del oro del suelo con cortes y fracciones por montón."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

from src.economy.taxes import TAX_POLICY_KEY, assess_tax, utc_day
from src.models.item_constants import GOLD_ITEM_ID
from src.utils.durability import require_durable
from src.utils.gold_atomic import operation_id
from src.utils.ground_state import MAX_GROUND_MAP_ID, GroundState
from src.utils.redis_config import RedisKeys
from src.utils.resource_transaction import Decision, Resource, Snapshot, transact

if TYPE_CHECKING:
    from redis.asyncio import Redis


def ground_map_id(resource: Resource) -> int:
    """Reconoce exclusivamente claves canónicas de suelo.

    Returns:
        Mapa válido o cero para otro tipo de recurso.
    """
    parts = resource.key.split(":")
    if (
        len(parts) != len(("ground_items", "map"))
        or parts[0] != "ground_items"
        or not parts[1].isdigit()
    ):
        return 0
    map_id = int(parts[1])
    return map_id if 1 <= map_id <= MAX_GROUND_MAP_ID else 0


@dataclass(frozen=True, slots=True)
class RemainderSplit:
    """Fracciones transferidas y retenidas de un saldo."""

    moved: int
    remaining: int


def split_remainder(remainder: int, amount: int, total: int) -> RemainderSplit:
    """Reparte fracciones sin crearlas ni descartarlas al mover oro.

    Returns:
        Partes que acompañan al monto transferido y permanecen en el origen.
    """
    moved = remainder * amount // total if total else 0
    return RemainderSplit(moved, remainder - moved)


def ground_projection(
    snapshot: Snapshot, resources: tuple[Resource, ...], today: int
) -> tuple[Snapshot, dict[str, str]]:
    """Liquida el suelo antes del negocio bajo su mismo WATCH/EXEC.

    Returns:
        Snapshot actualizado y escrituras sólo para los mapas que cambiaron.
    """
    policy = cast("dict[str, str]", snapshot[TAX_POLICY_KEY])
    activation = int(policy.get("ground_activation_day", policy["activation_day"]))
    rate = int(policy["rate_bps"]) if policy.get("enabled") == "1" else 0
    projected = dict(snapshot)
    writes: dict[str, str] = {}
    for resource in resources:
        map_id = ground_map_id(resource)
        raw = cast("str | None", snapshot.get(resource.key))
        if not map_id or not raw:
            continue
        ground = GroundState(map_id, raw)
        changed = False
        for tile in ground.tiles.values():
            for item in tile.copy():
                if item["item_id"] != GOLD_ITEM_ID:
                    continue
                previous = max(cast("int", item.get("devaluation_day", activation)), activation)
                result = assess_tax(
                    cast("int", item["quantity"]),
                    0,
                    previous,
                    today,
                    remainder=cast("int", item.get("devaluation_remainder", 0)),
                    rate_bps=rate,
                )
                fields = {
                    "quantity": result.wallet,
                    "devaluation_day": result.last_day,
                    "devaluation_remainder": result.remainder,
                }
                if any(item.get(key) != value for key, value in fields.items()):
                    item.update(fields)
                    changed = True
                if not result.wallet:
                    tile.remove(item)
        if changed:
            projected[resource.key] = writes[resource.key] = ground.encode()
    return projected, writes


def stamp_ground_gold(
    writes: Mapping[str, str | dict[str, str] | set[str]],
    resources: tuple[Resource, ...],
    today: int,
) -> dict[str, str | dict[str, str] | set[str]]:
    """Marca los montones nuevos después del negocio, sin antigüedad inventada.

    Returns:
        Escrituras con fecha y fracciones de cada moneda recién generada o movida.
    """
    result = dict(writes)
    for resource in resources:
        map_id = ground_map_id(resource)
        raw = writes.get(resource.key)
        if not map_id or not isinstance(raw, str):
            continue
        ground = GroundState(map_id, raw)
        for tile in ground.tiles.values():
            for item in tile:
                if item["item_id"] == GOLD_ITEM_ID:
                    item.setdefault("devaluation_day", today)
                    item.setdefault("devaluation_remainder", 0)
        result[resource.key] = ground.encode()
    return result


async def settle_ground_gold(redis: Redis, map_id: int) -> None:
    """Liquida mapas sin jugadores conservando el vencimiento original del suelo."""
    key = RedisKeys.ground_items(map_id)
    raw = await redis.get(key)
    if not raw or not await redis.exists(TAX_POLICY_KEY):
        return
    text = raw.decode() if isinstance(raw, bytes) else raw
    ground = GroundState(map_id, text)
    today = utc_day()
    pending = any(
        item["item_id"] == GOLD_ITEM_ID
        and ("devaluation_day" not in item or cast("int", item["devaluation_day"]) < today)
        for tile in ground.tiles.values()
        for item in tile
    )
    if not pending:
        return
    await require_durable(redis)
    await transact(
        redis,
        (Resource(key, "string", keep_ttl=True),),
        operation_id(),
        {"ground_devaluation": map_id},
        lambda _snapshot: Decision({"applied": True}, {}),
    )
    await require_durable(redis)
