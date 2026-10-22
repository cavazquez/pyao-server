"""Stock persistente y reposición por tiempo, sin reinicios que creen unidades."""

import json
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

from src.utils.gold_atomic import operation_id
from src.utils.redis_config import RedisKeys
from src.utils.resource_transaction import Decision, Resource, Snapshot, transact
from src.utils.slot_plan import MAX_SLOT_QUANTITY, SlotPlan

if TYPE_CHECKING:
    from redis.asyncio import Redis

MERCHANT_SLOTS = 20
DEFAULT_RESTOCK_SECONDS = 3600


@dataclass(frozen=True, slots=True)
class StockEntry:
    """Existencia inicial y límite de reposición de un artículo del catálogo."""

    item_id: int
    quantity: int
    increment: int


def catalog_key(npc_id: int) -> str:
    """Identifica la política persistida del mercader.

    Returns:
        Clave del catálogo y último período repuesto.
    """
    return f"merchant:{npc_id}:catalog"


def _read_policy(policy: dict[str, str]) -> tuple[list[list[int]], int, int]:
    """Valida la política persistida antes de calcular nuevas existencias.

    Returns:
        Artículos, intervalo y fecha del último período confirmado.

    Raises:
        ValueError: Si el formato o los límites no son compatibles.
    """
    try:
        items = json.loads(policy["items"])
        interval, last = int(policy["interval_seconds"]), int(policy["last_restock"])
        valid = (
            policy.get("version") == "1"
            and type(items) is list
            and len(items) <= MERCHANT_SLOTS
            and interval > 0
            and last >= 0
            and all(
                type(item) is list
                and len(item) == len(("id", "maximum", "increment"))
                and all(type(value) is int for value in item)
                and 1 <= item[0] <= MAX_SLOT_QUANTITY
                and all(0 <= value <= MAX_SLOT_QUANTITY for value in item[1:])
                for item in items
            )
        )
        if valid and len({item[0] for item in items}) == len(items):
            return cast("list[list[int]]", items), interval, last
    except KeyError, TypeError, ValueError:
        pass
    message = "Política comercial persistida inválida; no se modifica el stock"
    raise ValueError(message)


def stock_policy(policy: dict[str, str]) -> tuple[list[list[int]], int, int]:
    """Expone la política validada para la reposición administrativa explícita.

    Returns:
        Objetos, período y última reposición.
    """
    return _read_policy(policy)


def _validate_seed(entries: tuple[StockEntry, ...], interval_seconds: int) -> None:
    """Valida sólo la semilla que efectivamente se va a adoptar.

    Raises:
        ValueError: Si algún límite del nuevo catálogo es inválido.
    """
    if (
        not interval_seconds >= 1
        or len(entries) > MERCHANT_SLOTS
        or len({e.item_id for e in entries}) != len(entries)
        or any(
            not 1 <= e.item_id <= MAX_SLOT_QUANTITY
            or not 0 <= e.quantity <= MAX_SLOT_QUANTITY
            or not 0 <= e.increment <= MAX_SLOT_QUANTITY
            for e in entries
        )
    ):
        message = "Catálogo comercial fuera de rango"
        raise ValueError(message)


async def seed_merchant(
    redis: Redis,
    npc_id: int,
    entries: tuple[StockEntry, ...],
    *,
    interval_seconds: int = DEFAULT_RESTOCK_SECONDS,
    replace_catalog: bool = False,
    now: int | None = None,
) -> int:
    """Inicializa una sola vez; una recarga no borra ventas de los jugadores.

    Returns:
        Artículos configurados, preservando el inventario existente.

    Raises:
        ValueError: Si el catálogo inicial es inválido.
    """
    if npc_id < 1:
        message = "Mercader fuera de rango"
        raise ValueError(message)
    key, meta, index = (
        RedisKeys.merchant_inventory(npc_id),
        catalog_key(npc_id),
        f"merchant:{npc_id}:items",
    )
    encoded = json.dumps(
        [[e.item_id, e.quantity, e.increment] for e in entries], separators=(",", ":")
    )
    now = int(time.time()) if now is None else now

    def decide(snapshot: Snapshot) -> Decision:
        stock = cast("dict[str, str]", snapshot[key])
        policy = cast("dict[str, str]", snapshot[meta])
        if policy and not replace_catalog:
            # Redis es la autoridad: una actualización de TOML no modifica el mercado.
            configured, _interval, _last = _read_policy(policy)
            slots = SlotPlan(stock, MERCHANT_SLOTS, MAX_SLOT_QUANTITY)
            return Decision(
                {"configured": len(configured)},
                {
                    index: {str(s.item_id) for s in slots.slots.values()}
                    | {str(e[0]) for e in configured}
                },
            )
        _validate_seed(entries, interval_seconds)
        if policy:
            _read_policy(policy)
        writes: dict[str, str | dict[str, str] | set[str]] = {}
        if not stock and not policy:
            stock = {
                f"slot_{slot}": f"{entry.item_id}:{entry.quantity}" if entry.quantity else ""
                for slot, entry in enumerate(entries, 1)
            }
            writes[key] = stock
        slots = SlotPlan(stock, MERCHANT_SLOTS, MAX_SLOT_QUANTITY)
        writes[index] = {str(s.item_id) for s in slots.slots.values()} | {
            str(e.item_id) for e in entries
        }
        writes[meta] = {
            "version": "1",
            "revision": str(
                int(policy.get("revision", "1"))
                + int(
                    bool(policy)
                    and (
                        policy.get("items") != encoded
                        or policy.get("interval_seconds") != str(interval_seconds)
                    )
                )
            ),
            "items": encoded,
            "interval_seconds": str(interval_seconds),
            "last_restock": policy.get("last_restock", str(now)),
        }
        return Decision({"configured": len(entries)}, writes)

    result = await transact(
        redis,
        (Resource(key, "hash"), Resource(meta, "hash"), Resource(index, "set")),
        operation_id(),
        {
            "seed": npc_id,
            "items": encoded,
            "interval": interval_seconds,
            "migrate": replace_catalog,
        },
        decide,
    )
    return int(result["configured"])


async def restock_merchant(redis: Redis, npc_id: int, *, now: int | None = None) -> int:
    """Repone períodos pendientes sin sobrescribir compras o reventas concurrentes.

    Returns:
        Unidades agregadas, con trabajo acotado al catálogo de veinte slots.
    """
    now = int(time.time()) if now is None else now
    key, meta = RedisKeys.merchant_inventory(npc_id), catalog_key(npc_id)
    index = f"merchant:{npc_id}:items"

    def decide(snapshot: Snapshot) -> Decision:
        policy = cast("dict[str, str]", snapshot[meta])
        if not policy:
            return Decision({"added": 0}, {})
        items, interval, last = _read_policy(policy)
        periods = max(0, (now - last) // interval)
        if not periods:
            return Decision({"added": 0}, {})
        slots = SlotPlan(cast("dict[str, str]", snapshot[key]), MERCHANT_SLOTS, MAX_SLOT_QUANTITY)
        added = 0
        for item_id, maximum, increment in items:
            current = sum(s.quantity for s in slots.slots.values() if s.item_id == item_id)
            quantity = min(max(0, maximum - current), increment * periods)
            if quantity:
                try:
                    slots.give(item_id, quantity)
                except ValueError:
                    continue  # No se borran reventas para hacer espacio al catálogo.
                added += quantity
        return Decision(
            {"added": added},
            {
                key: slots.fields(),
                meta: {"last_restock": str(last + periods * interval)},
                index: cast("set[str]", snapshot[index])
                | {str(s.item_id) for s in slots.slots.values()},
            },
        )

    result = await transact(
        redis,
        (Resource(key, "hash"), Resource(meta, "hash"), Resource(index, "set")),
        operation_id(),
        {"restock": npc_id, "at": now},
        decide,
    )
    return int(result["added"])
