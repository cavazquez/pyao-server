"""Mutaciones relativas y swap que comparten WATCH con banco, comercio y pickup."""

from typing import TYPE_CHECKING, Any, Literal, cast

from src.utils.gold_atomic import operation_id
from src.utils.redis_config import RedisKeys
from src.utils.resource_transaction import Decision, Resource, Snapshot, transact
from src.utils.slot_plan import SlotPlan

if TYPE_CHECKING:
    from redis.asyncio import Redis

Mode = Literal["add", "remove", "remove_by_id", "swap"]


def _apply(plan: SlotPlan, equipment: dict[str, str], mode: Mode, values: tuple[int, int]) -> None:
    """Aplica cambios sólo sobre la copia local.

    Raises:
        ValueError: Ante recursos insuficientes o intento de consumir equipo activo.
    """
    first, second = values
    if mode == "add":
        plan.give(first, second)
    elif mode == "remove":
        stack = plan.slots.get(first)
        plan.take(first, stack.item_id if stack else 0, second)
    elif mode == "remove_by_id":
        remaining = second
        for slot, stack in sorted(plan.slots.copy().items()):
            if stack.item_id != first or remaining == 0:
                continue
            amount = min(remaining, stack.quantity)
            plan.take(slot, first, amount)
            remaining -= amount
        if remaining:
            msg = "No hay objetos suficientes"
            raise ValueError(msg)
    else:
        original, destination = plan.slots.get(first), plan.slots.get(second)
        for slot in values:
            plan.slots.pop(slot, None)
        if original:
            plan.slots[second] = original
        if destination:
            plan.slots[first] = destination
        for field, reference in equipment.items():
            if reference == str(first):
                equipment[field] = str(second)
            elif reference == str(second):
                equipment[field] = str(first)
    if mode in {"remove", "remove_by_id"} and any(
        slot.isdigit() and int(slot) > 0 and int(slot) not in plan.slots
        for slot in equipment.values()
    ):
        msg = "Desequipá el objeto antes de retirarlo"
        raise ValueError(msg)


async def change_inventory(
    redis: Redis, user_id: int, mode: Mode, values: tuple[int, int], capacity: int, max_stack: int
) -> dict[str, Any]:
    """Confirma campos y referencias de equipo juntos sin pisar otras operaciones.

    Returns:
        Slots y equipo efectivos del commit o rechazo sin cambios.
    """
    if any(type(value) is not int for value in values):
        return {"applied": False, "error": "Datos de inventario inválidos"}
    if mode == "swap" and not all(1 <= slot <= capacity for slot in values):
        return {"applied": False, "error": "Slot fuera de rango"}
    key, equipment_key = RedisKeys.player_inventory(user_id), RedisKeys.player_equipment(user_id)
    selected_item: int | None = None

    def decide(snapshot: Snapshot) -> Decision:
        nonlocal selected_item
        try:
            plan = SlotPlan(cast("dict[str, str]", snapshot[key]), capacity, max_stack)
            before = plan.fields()
            equipment = cast("dict[str, str]", snapshot[equipment_key]).copy()
            if mode == "remove":
                item = plan.slots.get(values[0])
                current_item = item.item_id if item else 0
                selected_item = current_item if selected_item is None else selected_item
                if current_item != selected_item:
                    return Decision({"applied": False, "error": "El objeto del slot cambió"}, {})
            _apply(plan, equipment, mode, values)
        except ValueError as error:
            return Decision({"applied": False, "error": str(error)}, {})
        after = plan.fields()
        changed = [
            slot
            for slot in range(1, capacity + 1)
            if before[f"slot_{slot}"] != after[f"slot_{slot}"]
        ]
        slots = [
            [slot, plan.slots[slot].item_id, plan.slots[slot].quantity]
            if slot in plan.slots
            else [slot, 0, 0]
            for slot in changed
        ]
        result = {
            "applied": True,
            "slots": slots,
            "first": after.get(f"slot_{values[0]}", ""),
            "second": after.get(f"slot_{values[1]}", ""),
            "first_equipped": str(values[0]) in equipment.values(),
            "second_equipped": str(values[1]) in equipment.values(),
        }
        return Decision(result, {key: after, equipment_key: equipment})

    return await transact(
        redis,
        (Resource(key, "hash"), Resource(equipment_key, "hash")),
        operation_id(),
        {"mode": mode, "values": values},
        decide,
        receipt_ttl_seconds=30,
        retry_window_seconds=10,
    )
