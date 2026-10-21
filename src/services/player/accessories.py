"""Una ranura para el ObjType 18 real: anillos, focos musicales y guantes."""

from functools import cache
from typing import TYPE_CHECKING, Any, cast

from src.models.character_class import ClassCatalog
from src.models.item_catalog import ItemCatalog
from src.models.item_types import ObjType
from src.services.action_resources import player_action_resources
from src.utils.gold_atomic import operation_id
from src.utils.inventory_slot import InventorySlot
from src.utils.redis_config import RedisKeys
from src.utils.resource_transaction import Decision, Snapshot, transact

if TYPE_CHECKING:
    from src.utils.redis_client import RedisClient


@cache
def catalogues() -> tuple[ItemCatalog, ClassCatalog]:
    """Carga tablas estáticas una sola vez por proceso.

    Returns:
        Catálogos propios de objetos y clases.
    """
    return ItemCatalog(), ClassCatalog()


async def toggle_accessory(redis: RedisClient, user: int, inventory_slot: int) -> dict[str, Any]:
    """Confirma el slot observado, las restricciones y el reemplazo en un solo EXEC.

    Returns:
        Estado confirmado para actualizar la interfaz sin acumular modificadores.
    """
    catalog, classes = catalogues()
    equipment_key = RedisKeys.player_equipment(user)

    def decide(snapshot: Snapshot) -> Decision:
        gear = cast("dict[str, str]", snapshot[equipment_key])
        bag = cast("dict[str, str]", snapshot[RedisKeys.player_inventory(user)])
        stats = cast("dict[str, str]", snapshot[RedisKeys.player_user_stats(user)])
        stack = InventorySlot.parse(bag.get(f"slot_{inventory_slot}", ""))
        item = catalog.get_item_data(stack.item_id) if stack else None
        if not item or item.get("ObjType") != ObjType.ANILLOS:
            return Decision({"applied": False, "message": "El accesorio de ese slot cambió."}, {})
        equipped = gear.get("accessory") == str(inventory_slot)
        if not equipped:
            character_class = classes.get_class(int(stats.get("class_id", 0)))
            forbidden = cast("list[str]", item.get("ClasesProhibidas", []))
            if int(stats.get("min_hp", 0)) <= 0:
                return Decision({"applied": False, "message": "Debes estar vivo para equipar."}, {})
            if forbidden and (character_class is None or character_class.name.upper() in forbidden):
                return Decision(
                    {"applied": False, "message": "Tu clase no puede equipar ese accesorio."}, {}
                )
        return Decision(
            {
                "applied": True,
                "equipped": not equipped,
                "item_id": stack.item_id if stack else 0,
                "name": str(item["Name"]),
                "magic_min": int(str(item.get("DefensaMagicaMin", 0))),
                "magic_max": int(str(item.get("DefensaMagicaMax", 0))),
                "focus_power": int(str(item.get("StaffPower", 0))),
            },
            {equipment_key: {"accessory": "0" if equipped else str(inventory_slot)}},
        )

    return await transact(
        redis.redis,
        player_action_resources(user),
        operation_id(),
        {"accessory": user, "slot": inventory_slot},
        decide,
    )
