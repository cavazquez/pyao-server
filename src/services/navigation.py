"""Navegación manual: valida la embarcación real y persiste su estado en Redis."""

import math
from typing import TYPE_CHECKING, Any, cast

from src.services.action_resources import player_action_resources
from src.services.combat_snapshot import levels
from src.utils.redis_config import RedisKeys
from src.utils.resource_transaction import Decision, Snapshot, transact
from src.utils.slot_plan import SlotPlan

BOAT_TYPE = 31
PIRATE_CLASS = 12
WORKER_CLASS = 11
MAX_COORD = 100


if TYPE_CHECKING:
    from collections.abc import Mapping

    from src.models.item_catalog import ItemCatalog
    from src.repositories.inventory_repository import InventoryRepository
    from src.repositories.player_repository import PlayerRepository
    from src.services.map.map_resources_service import MapResourcesService


def required_navigation(
    boat: Mapping[str, object], stats: Mapping[str, str], skills: Mapping[str, int]
) -> int:
    """Comparte el requisito de embarcación entre uso manual y portales.

    Returns:
        Puntos de Navegación necesarios para esa clase y embarcación.
    """
    player_class = int(stats.get("class_id", 0))
    modifier = (
        1.0
        if player_class == PIRATE_CLASS
        else 1.71
        if player_class == WORKER_CLASS and skills["pesca"] == MAX_COORD
        else 2.0
    )
    return math.ceil(int(str(boat.get("MinSkill", 35))) * modifier)


async def navigate(
    player: PlayerRepository,
    inventory: InventoryRepository,
    catalog: ItemCatalog,
    terrain: MapResourcesService,
    user: int,
    slot: int,
    identity: str,
) -> dict[str, Any]:
    """Alterna únicamente con barco disponible, conocimiento suficiente y costa válida.

    Returns:
        Estado confirmado y requisito de la embarcación; no concede XP natural.
    """
    key = RedisKeys.player_user_stats(user)

    def decide(snapshot: Snapshot) -> Decision:
        stats = cast("dict[str, str]", snapshot[key])
        slots = SlotPlan(
            cast("dict[str, str]", snapshot[RedisKeys.player_inventory(user)]),
            inventory.MAX_SLOTS,
            inventory.stacking.max_stack,
        )
        boat_stack = slots.slots.get(slot)
        boat = catalog.get_item_data(boat_stack.item_id) if boat_stack else None
        if not boat or boat.get("ObjType") != BOAT_TYPE or int(stats.get("min_hp", 0)) <= 0:
            return Decision(
                {"applied": False, "message": "Debes estar vivo y tener una embarcación válida."},
                {},
            )
        skills = levels(snapshot, user)
        required = required_navigation(boat, stats, skills)
        sailing = stats.get("sailing") == "1"
        if not sailing and skills["navegacion"] < required:
            return Decision(
                {
                    "applied": False,
                    "message": f"Necesitas {required} puntos de Navegación para esta embarcación.",
                    "required": required,
                },
                {},
            )
        pos = cast("dict[str, str]", snapshot[RedisKeys.player_position(user)])
        map_id, x, y = (int(pos.get(k, 0)) for k in ("map", "x", "y"))
        water = any(
            terrain.has_water(map_id, tx, ty)
            for tx in range(x - 1, x + 2)
            for ty in range(y - 1, y + 2)
        )
        coast = any(
            1 <= tx <= MAX_COORD
            and 1 <= ty <= MAX_COORD
            and not terrain.has_water(map_id, tx, ty)
            and not terrain.is_blocked(map_id, tx, ty)
            for tx in range(x - 1, x + 2)
            for ty in range(y - 1, y + 2)
        )
        if (not sailing and not water) or (sailing and not coast):
            return Decision(
                {
                    "applied": False,
                    "message": "Debes estar junto a la costa para embarcar o desembarcar.",
                },
                {},
            )
        return Decision(
            {
                "applied": True,
                "sailing": not sailing,
                "boat": boat_stack.item_id if boat_stack else 0,
                "message": "Has comenzado a navegar." if not sailing else "Has desembarcado.",
            },
            {
                key: {
                    "sailing": "0" if sailing else "1",
                    "boat_slot": str(slot),
                    "boat_item": str(boat_stack.item_id if boat_stack else 0),
                    "hidden_until": "0",
                }
            },
        )

    return await transact(
        player.redis.redis,
        player_action_resources(user),
        identity,
        {"navigate": user, "slot": slot},
        decide,
    )
