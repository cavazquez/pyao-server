"""Consultas puras al equipo y habilidades de un snapshot de combate."""

import time
from typing import TYPE_CHECKING, cast

from src.items.condition import effective
from src.items.ledger import PREFIX
from src.models.skills import skill_progress
from src.utils.inventory_slot import InventorySlot
from src.utils.redis_config import RedisKeys

if TYPE_CHECKING:
    from src.models.item_catalog import ItemCatalog
    from src.utils.resource_transaction import Snapshot


def levels(snapshot: Snapshot, user: int) -> dict[str, int]:
    """Obtiene niveles canónicos sin usar la XP acumulada como poder de combate.

    Returns:
        Niveles de todas las habilidades, incluidas las extensiones propias.
    """
    return {
        p.definition.key: p.level
        for p in skill_progress(cast("dict[str, str]", snapshot[RedisKeys.player_skills(user)]))
        if p.definition.key is not None
    }


def equipped(snapshot: Snapshot, user: int, slot: str, catalog: ItemCatalog) -> dict[str, object]:
    """Resuelve el objeto equipado desde inventario y equipo observados juntos.

    Returns:
        Datos del objeto real, o vacío para un slot sin equipar.
    """
    gear = cast("dict[str, str]", snapshot[RedisKeys.player_equipment(user)])
    bag = cast("dict[str, str]", snapshot[RedisKeys.player_inventory(user)])
    value = bag.get(f"slot_{gear.get(slot, '0')}", "")
    stack = InventorySlot.parse(value)
    base = catalog.get_item_data(stack.item_id) or {} if stack else {}
    if stack and stack.instance_ids:
        state = snapshot.get(PREFIX + stack.instance_ids[0])
        if isinstance(state, dict):
            result = effective(base, state, int(str(snapshot.get("items:now") or int(time.time()))))
            return result if slot == "weapon" or not result["_broken"] else {}
    return base
