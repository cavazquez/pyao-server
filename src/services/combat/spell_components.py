"""Consumo puro de componentes o materiales de misión, sin equipo puesto."""

from collections.abc import Iterable, Mapping

from src.utils.slot_plan import SlotPlan

INVENTORY_CAPACITY = 30
MAX_QUANTITY = 32767


def take_materials(
    values: dict[str, str], gear: Mapping[str, str], requirements: Iterable[tuple[int, int]]
) -> dict[str, str]:
    """Prepara todos los materiales en memoria; el llamador confirma sólo el total.

    Returns:
        Campos completos de inventario después del consumo.

    Raises:
        ValueError: Si falta un material sin equipar; no se escribió ningún dato.
    """
    bag = SlotPlan(values, INVENTORY_CAPACITY, MAX_QUANTITY)
    equipped = {int(value) for value in gear.values() if value.isdecimal()}
    for item_id, quantity in requirements:
        left = quantity
        for slot, stack in sorted(bag.slots.items()):
            if stack.item_id == item_id and slot not in equipped:
                count = min(left, stack.quantity)
                if count:
                    bag.take(slot, item_id, count)
                    left -= count
            if not left:
                break
        if left:
            message = "No tienes los componentes u objetos requeridos sin equipar."
            raise ValueError(message)
    return bag.fields()
