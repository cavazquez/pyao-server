"""Lectura coherente y paginada del equipo autorizado, sin escanear el mundo."""

from typing import TYPE_CHECKING, Any, cast

from redis.exceptions import WatchError

from src.items import ledger
from src.items.condition import condition, effective
from src.items.policy import STAT_FIELDS
from src.models.item_catalog import ItemCatalog
from src.utils.inventory_slot import InventorySlot
from src.utils.resource_transaction import Resource, _read_snapshot

if TYPE_CHECKING:
    from redis.asyncio import Redis
    from redis.asyncio.client import Pipeline

    from src.utils.resource_transaction import Snapshot

PAGE_SIZE = 5
CATALOG = ItemCatalog()


def project(item_id: int, state: dict[str, str], now: int) -> dict[str, Any]:
    """Proyecta base y valores efectivos sin modificar el catálogo compartido.

    Returns:
        Estado validado de la operación, sin alterar los datos del catálogo.
    """
    base = CATALOG.get_item_data(item_id) or {}
    current = effective(base, state, now)
    quality, factor, broken = condition(state, now)
    return {
        "id": state["id"],
        "item": item_id,
        "version": int(state["version"]),
        "created": int(state["created_at"]),
        "expires": int(state["expires_at"]),
        "uses": int(state["uses_spent"]),
        "max_uses": int(state["max_uses"]),
        "condition": quality,
        "factor": factor,
        "broken": broken,
        "base": {k: int(str(base[k])) for k in sorted(STAT_FIELDS & base.keys())},
        "effective": {k: int(str(current[k])) for k in sorted(STAT_FIELDS & base.keys())},
    }


async def _observe_previews(
    pipe: Pipeline, snapshot: Snapshot, scopes: dict[str, tuple[str, tuple[int, ...]]]
) -> None:
    """Observa sólo el siguiente ejemplar de cada slot comercial, sin leer todo el stock.

    Raises:
        ValueError: Si una referencia no corresponde al contenedor observado.
    """
    pending = {}
    for key, slots in scopes.values():
        bag = cast("dict[str, str]", snapshot[key])
        for slot in slots:
            stack = InventorySlot.parse(bag.get(f"slot_{slot}", ""))
            if (
                stack
                and stack.instance_ids
                and ledger.PREFIX + stack.instance_ids[0] not in snapshot
            ):
                pending[stack.instance_ids[0]] = (stack.item_id, f"{key}|slot_{slot}")
    if pending:
        await pipe.watch(*(ledger.PREFIX + iid for iid in pending))
        data = await ledger.read_states(pipe, [ledger.PREFIX + iid for iid in pending])
        for (iid, (item, location)), flat in zip(pending.items(), data[1:], strict=True):
            state = dict(zip(flat[::2], flat[1::2], strict=True))
            if state.get("location") != location or state.get("item_id") != str(item):
                message = "Estado comercial individual inválido"
                raise ValueError(message)
            snapshot[ledger.PREFIX + iid] = state


async def pages(
    redis: Redis, scopes: dict[str, tuple[str, tuple[int, ...]]]
) -> list[dict[str, Any]]:
    """Lee sólo slots propios/abiertos/ofrecidos y verifica WATCH al terminar.

    Returns:
        Estado validado de la operación, sin alterar los datos del catálogo.

    Raises:
        RuntimeError: Si el estado persistido o la operación no son válidos.
    """
    resources = tuple(
        Resource(key, "hash") for key in dict.fromkeys(key for key, _ in scopes.values())
    )
    for _ in range(8):
        async with redis.pipeline() as pipe:
            try:
                await pipe.watch(*(r.key for r in resources))
                snapshot = await _read_snapshot(pipe, resources)
                now, _ = await ledger.prepare(pipe, snapshot, resources)
                await _observe_previews(pipe, snapshot, scopes)
                result: list[dict[str, Any]] = []
                for scope, (key, slots) in scopes.items():
                    bag = cast("dict[str, str]", snapshot[key])
                    rows = []
                    for slot in slots:
                        stack = InventorySlot.parse(bag.get(f"slot_{slot}", ""))
                        state = (
                            snapshot.get(ledger.PREFIX + stack.instance_ids[0])
                            if stack and stack.instance_ids
                            else None
                        )
                        rows.append(
                            [
                                slot,
                                {
                                    **project(stack.item_id, state, now),
                                    **(
                                        {"preview": True, "quantity": stack.quantity}
                                        if scope == "merchant"
                                        else {}
                                    ),
                                }
                                if stack and isinstance(state, dict)
                                else {},
                            ]
                        )
                    result.extend(
                        {
                            "scope": scope,
                            "page": offset // PAGE_SIZE,
                            "clock": now,
                            "rows": rows[offset : offset + PAGE_SIZE],
                        }
                        for offset in range(0, len(rows), PAGE_SIZE)
                    )
                pipe.multi()  # type: ignore[no-untyped-call]
                await pipe.execute()
            except WatchError:
                continue
            except ValueError:
                try:
                    pipe.multi()  # type: ignore[no-untyped-call]
                    await pipe.execute()
                except WatchError:
                    continue
                raise
            else:
                return result
    msg = "El inventario cambió durante la consulta; volver a consultar"
    raise RuntimeError(msg)
