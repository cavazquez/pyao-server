"""Identidades y estado individual confirmados con las mismas transacciones de negocio."""

import json
import time
from hashlib import sha256
from typing import TYPE_CHECKING, Any, cast

from src.items.policy import individual, policy_for
from src.utils.inventory_slot import InventorySlot

if TYPE_CHECKING:
    from redis.asyncio.client import Pipeline

    from src.utils.resource_transaction import Decision, Resource, Snapshot

FORMAT_KEY = "items:format_version"
CLOCK_KEY = "items:clock"
PREFIX = "item:instance:"
MARKER = "__item_instances__"
# La única escritura fuera del EXEC es un reloj creciente; nunca cambia oro u objetos.
_READ = """
local now = math.max(tonumber(ARGV[1]), tonumber(redis.call('GET', KEYS[1]) or '0'))
redis.call('SET', KEYS[1], now)
local result = {tostring(now)}
for i=2,#KEYS do result[#result+1] = redis.call('HGETALL', KEYS[i]) end
return result
"""


def container(key: str) -> bool:
    """Reconoce únicamente contenedores del inventario canónico.

    Returns:
        Estado validado de la operación, sin alterar los datos del catálogo.
    """
    return (
        key.endswith(":inventory")
        or (key.startswith("bank:") and key.endswith(":vault"))
        or (key.startswith("clan:depot:") and key.removeprefix("clan:depot:").isdigit())
    )


def personal(key: str) -> bool:
    """Los inventarios y bancos de jugadores no apilan equipo individual.

    Returns:
        Estado validado de la operación, sin alterar los datos del catálogo.
    """
    return key.startswith(("player:", "bank:"))


def references(snapshot: Snapshot, resources: tuple[Resource, ...]) -> dict[str, tuple[int, str]]:
    """Enumera identidades una vez; rechaza referencias duplicadas o slots corruptos.

    Returns:
        Estado validado de la operación, sin alterar los datos del catálogo.

    Raises:
        ValueError: Si el estado persistido o la operación no son válidos.
    """
    result: dict[str, tuple[int, str]] = {}
    for resource in resources:
        value = snapshot.get(resource.key)
        rows: list[tuple[str, int, tuple[str, ...]]] = []
        if container(resource.key) and isinstance(value, dict):
            for field, raw in value.items():
                if not field.startswith("slot_") or not raw:
                    continue
                slot = InventorySlot.parse(raw)
                if slot is None:
                    msg = "Slot de objeto inválido"
                    raise ValueError(msg)
                rows.append((field, slot.item_id, slot.instance_ids))
        elif resource.kind == "ground" and isinstance(value, str):
            for coordinate, tile in json.loads(value).items():
                rows.extend(
                    (
                        f"{coordinate}/{item['stack_id']}",
                        item["item_id"],
                        tuple(item.get("instance_ids", [])),
                    )
                    for item in tile
                )
        for field, item_id, ids in rows:
            for iid in ids:
                if iid in result:
                    msg = "Identidad de objeto duplicada"
                    raise ValueError(msg)
                result[iid] = (item_id, f"{resource.key}|{field}")
    return result


def new_state(iid: str, item_id: int, location: str, now: int) -> dict[str, str]:
    """Congela la política de nacimiento para no rejuvenecer al cambiar el balance.

    Returns:
        Estado validado de la operación, sin alterar los datos del catálogo.
    """
    policy = policy_for(item_id)
    return {
        "id": iid,
        "item_id": str(item_id),
        "created_at": str(now),
        "last_seen": str(now),
        "expires_at": str(now + policy.lifetime_seconds) if policy.lifetime_seconds else "0",
        "lifetime_seconds": str(policy.lifetime_seconds),
        "max_uses": str(policy.max_uses),
        "uses_spent": "0",
        "minimum_factor_bps": str(policy.minimum_factor_bps),
        "policy_version": str(policy.version),
        "version": "1",
        "location": location,
    }


async def read_states(pipe: Pipeline, keys: list[str]) -> list[Any]:
    """Lee todos los hashes y el reloj en una sola llamada Lua.

    Returns:
        Reloj y campos completos de cada identidad en orden.
    """
    return cast(
        "list[Any]", await pipe.eval(_READ, len(keys) + 1, CLOCK_KEY, *keys, int(time.time()))
    )


async def prepare(
    pipe: Pipeline, snapshot: Snapshot, resources: tuple[Resource, ...]
) -> tuple[int, dict[str, tuple[int, str]]]:
    """Observa los metadatos antes de decidir; una transferencia concurrente invalida WATCH.

    Returns:
        Estado validado de la operación, sin alterar los datos del catálogo.

    Raises:
        ValueError: Si el estado persistido o la operación no son válidos.
    """
    refs = references(snapshot, resources)
    # El stock puede contener miles de ejemplares. Sólo el equipo del jugador
    # interviene en las reglas previas; las unidades comerciales que se muevan
    # se observan después de decidir, antes del mismo EXEC.
    observed = {iid: value for iid, value in refs.items() if personal(value[1].split("|", 1)[0])}
    keys = [PREFIX + iid for iid in observed]
    if keys:
        await pipe.watch(*keys)
    data = await read_states(pipe, keys)
    now = int(data[0])
    for (iid, (item_id, location)), flat in zip(observed.items(), data[1:], strict=True):
        state = dict(zip(flat[::2], flat[1::2], strict=True))
        if (
            state.get("id") != iid
            or state.get("item_id") != str(item_id)
            or state.get("location") != location
        ):
            msg = "Propietario o estado individual inválido; no se modificaron objetos"
            raise ValueError(msg)
        snapshot[PREFIX + iid] = state
    snapshot["items:now"] = str(now)
    for resource in resources:
        value = snapshot.get(resource.key)
        if container(resource.key) and personal(resource.key) and isinstance(value, dict):
            value[MARKER] = "1"
    return now, refs


def _normalize(
    snapshot: Snapshot, resources: tuple[Resource, ...], identity: str, writes: dict[str, Any]
) -> None:
    """Da identidad a creaciones; nunca sustituye una identidad transferida explícitamente.

    Raises:
        ValueError: Si el estado persistido o la operación no son válidos.
    """
    for resource in resources:
        if resource.key not in writes:
            continue
        value = writes[resource.key]
        if container(resource.key) and isinstance(value, dict):
            merged = {**cast("dict[str, str]", snapshot[resource.key]), **value}
            capacity = (
                40
                if resource.key.startswith("bank:")
                else 30
                if resource.key.startswith("player:")
                else max([int(k[5:]) for k in merged if k.startswith("slot_")] or [20])
            )
            for field, raw in list(merged.items()):
                if not field.startswith("slot_") or not raw:
                    continue
                slot = InventorySlot.parse(raw)
                if slot is None or not individual(slot.item_id) or slot.instance_ids:
                    continue
                ids = tuple(
                    sha256(f"{identity}|{resource.key}|{field}|{index}".encode()).hexdigest()[:32]
                    for index in range(slot.quantity)
                )
                if personal(resource.key) and slot.quantity > 1:
                    empty = [
                        f"slot_{i}" for i in range(1, capacity + 1) if not merged.get(f"slot_{i}")
                    ]
                    if len(empty) < slot.quantity - 1:
                        msg = "El equipo individual no cabe: liberá slots antes de migrar"
                        raise ValueError(msg)
                    for target, iid in zip([field, *empty[: slot.quantity - 1]], ids, strict=True):
                        merged[target] = InventorySlot(slot.item_id, 1, (iid,)).to_string()
                else:
                    merged[field] = InventorySlot(slot.item_id, slot.quantity, ids).to_string()
            writes[resource.key] = {
                **value,
                **{k: v for k, v in merged.items() if k.startswith("slot_")},
                **({MARKER: "1"} if personal(resource.key) else {}),
            }
        elif resource.kind == "ground" and isinstance(value, str):
            tiles = json.loads(value)
            for tile in tiles.values():
                for item in tile:
                    if individual(item["item_id"]) and not item.get("instance_ids"):
                        item["instance_ids"] = [
                            sha256(f"{identity}|{item['stack_id']}|{i}".encode()).hexdigest()[:32]
                            for i in range(item["quantity"])
                        ]
            writes[resource.key] = json.dumps(tiles, separators=(",", ":"))


async def finish(  # ruff: ignore[too-many-locals] - una sola proyección de todas las ubicaciones observadas.
    pipe: Pipeline,
    snapshot: Snapshot,
    resources: tuple[Resource, ...],
    identity: str,
    decision: Decision,
    now: int,
    before: dict[str, tuple[int, str]],
) -> tuple[Decision, tuple[Resource, ...]]:
    """Incluye ubicación, creación y desgaste en el EXEC y en su recibo idempotente.

    Returns:
        Estado validado de la operación, sin alterar los datos del catálogo.

    Raises:
        ValueError: Si el estado persistido o la operación no son válidos.
    """
    from src.utils.resource_transaction import Decision, Resource  # ruff: ignore[import-outside-top-level] - evita ciclo con el ejecutor de transacciones.

    writes = dict(decision.writes)
    result = decision.result.copy()
    uses = result.pop("_item_uses", {})
    _normalize(snapshot, resources, identity, writes)
    after_snapshot = snapshot.copy()
    for key, value in writes.items():
        previous = snapshot.get(key)
        after_snapshot[key] = (
            {**previous, **value}
            if isinstance(previous, dict) and isinstance(value, dict)
            else value
        )
    after = references(after_snapshot, resources)
    changed = {
        iid
        for iid in before.keys() | after.keys()
        if before.get(iid) != after.get(iid) or uses.get(iid)
    }
    pending = [iid for iid in changed if iid in before and PREFIX + iid not in snapshot]
    if pending:
        await pipe.watch(*(PREFIX + iid for iid in pending))
        states = await read_states(pipe, [PREFIX + iid for iid in pending])
        now = max(now, int(states[0]))
        for iid, flat in zip(pending, states[1:], strict=True):
            state = dict(zip(flat[::2], flat[1::2], strict=True))
            if state.get("location") != before[iid][1] or state.get("item_id") != str(
                before[iid][0]
            ):
                msg = "La propiedad del objeto transferido es inválida"
                raise ValueError(msg)
            snapshot[PREFIX + iid] = state
    # Si desapareció una referencia, sólo puede consumirse/retirarse, nunca reaparecer nueva.
    created = [iid for iid in after if iid not in before]
    if created:
        await pipe.watch(*(PREFIX + iid for iid in created))
        if await pipe.exists(*(PREFIX + iid for iid in created)):
            msg = "Identidad individual ya utilizada"
            raise ValueError(msg)
    additions = []
    for iid in changed:
        key = PREFIX + iid
        if iid in before:
            state = cast("dict[str, str]", snapshot[key]).copy()
        else:
            item_id, location = after[iid]
            state = new_state(iid, item_id, location, now)
            snapshot[key] = {}
        location = after[iid][1] if iid in after else "retired"
        spent = uses.pop(iid, 0)
        if type(spent) is not int or spent < 0:
            msg = "Consumo de usos inválido"
            raise ValueError(msg)
        if state["location"] != location or spent or iid not in before:
            state.update(
                location=location,
                last_seen=str(max(now, int(state["last_seen"]))),
                uses_spent=str(int(state["uses_spent"]) + spent),
                version=str(int(state["version"]) + (iid in before)),
            )
            writes[key] = state
        additions.append(
            Resource(key, "hash", ttl_seconds=604800 if location == "retired" else None)
        )
    if uses:
        msg = "No se puede desgastar un objeto ajeno a la transacción"
        raise ValueError(msg)
    return Decision(result, writes), (*resources, *additions)
