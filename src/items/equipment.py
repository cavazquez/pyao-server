"""Equipamiento confirmado junto con identidad, estado y restricciones de clase."""

from typing import TYPE_CHECKING, Any, cast

from src.items.condition import condition
from src.items.ledger import PREFIX
from src.models.character_class import ClassCatalog
from src.models.item_catalog import ItemCatalog
from src.models.items_catalog import ITEMS_CATALOG
from src.services.action_resources import player_action_resources
from src.utils.gold_atomic import operation_id
from src.utils.inventory_slot import InventorySlot
from src.utils.redis_config import RedisKeys
from src.utils.resource_transaction import Decision, Snapshot, transact

if TYPE_CHECKING:
    from redis.asyncio import Redis

    from src.utils.equipment_slot import EquipmentSlot

CLASSES = ClassCatalog()
CATALOG = ItemCatalog()


async def toggle(redis: Redis, user: int, slot: int, layer: EquipmentSlot) -> dict[str, Any]:
    """Permite retirar un objeto roto; rechaza equiparlo o usar equipo cambiado.

    Returns:
        Estado validado de la operación, sin alterar los datos del catálogo.
    """
    key = RedisKeys.player_equipment(user)

    def decide(snapshot: Snapshot) -> Decision:
        gear = cast("dict[str, str]", snapshot[key])
        bag = cast("dict[str, str]", snapshot[RedisKeys.player_inventory(user)])
        stats = cast("dict[str, str]", snapshot[RedisKeys.player_user_stats(user)])
        stack = InventorySlot.parse(bag.get(f"slot_{slot}", ""))
        item = ITEMS_CATALOG.get(stack.item_id) if stack else None
        if item is None or item.item_type.value != layer.value:
            return Decision({"applied": False, "message": "El objeto del slot cambió."}, {})
        removing = gear.get(layer.value) == str(slot)
        if not removing:
            if int(stats.get("min_hp", 0)) <= 0:
                return Decision({"applied": False, "message": "Debes estar vivo para equipar."}, {})
            state = (
                snapshot.get(PREFIX + stack.instance_ids[0])
                if stack and stack.instance_ids
                else None
            )
            if isinstance(state, dict) and condition(state, int(str(snapshot["items:now"])))[2]:
                return Decision(
                    {"applied": False, "message": "El objeto está roto y no aporta estadísticas."},
                    {},
                )
            raw = CATALOG.get_item_data(item.item_id) or {}
            forbidden = cast("list[str]", raw.get("ClasesProhibidas", []))
            character_class = CLASSES.get_class(int(stats.get("class_id", 0)))
            if (
                layer.value == "boots"
                and forbidden
                and (character_class is None or character_class.name.upper() in forbidden)
            ):
                return Decision(
                    {"applied": False, "message": "Tu clase no puede equipar ese objeto."}, {}
                )
        return Decision(
            {"applied": True, "equipped": not removing, "name": item.name},
            {key: {layer.value: "0" if removing else str(slot)}},
        )

    return await transact(
        redis,
        player_action_resources(user),
        operation_id(),
        {"equip": slot, "layer": layer.value},
        decide,
    )
