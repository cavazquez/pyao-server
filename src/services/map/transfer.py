"""Confirma posición y navegación juntas, sobre el origen e inventario observados."""

from typing import TYPE_CHECKING, Any, cast

from src.services.action_resources import player_action_resources
from src.services.combat_snapshot import levels
from src.services.navigation import BOAT_TYPE, required_navigation
from src.utils.inventory_slot import InventorySlot
from src.utils.redis_config import RedisKeys
from src.utils.resource_transaction import Decision, Snapshot, transact

if TYPE_CHECKING:
    from src.models.item_catalog import ItemCatalog
    from src.repositories.player_repository import PlayerRepository


async def commit_transfer(
    player: PlayerRepository,
    catalog: ItemCatalog,
    user: int,
    origin: tuple[int, int, int],
    destination: tuple[int, int, int],
    heading: int,
    water: bool,
    identity: str,
) -> dict[str, Any]:
    """Rechaza un origen cambiado o embarcación inválida sin escribir estado parcial.

    Returns:
        Confirmación y estado de navegación del mismo commit Redis.
    """
    position_key = RedisKeys.player_position(user)
    stats_key = RedisKeys.player_user_stats(user)

    def decide(snapshot: Snapshot) -> Decision:
        position = cast("dict[str, str]", snapshot[position_key])
        stats = cast("dict[str, str]", snapshot[stats_key])
        actual = tuple(int(position.get(key, 0)) for key in ("map", "x", "y"))
        if actual != origin:
            return Decision({"applied": False, "message": "Tu posición ya cambió."}, {})
        was_sailing = stats.get("sailing") == "1"
        navigation = {"sailing": "1" if water else "0"}
        if water:
            if int(stats.get("min_hp", 0)) <= 0:
                return Decision({"applied": False, "message": "Debes estar vivo para navegar."}, {})
            skills = levels(snapshot, user)
            inventory = cast("dict[str, str]", snapshot[RedisKeys.player_inventory(user)])
            for slot, encoded in sorted(inventory.items()):
                stack = InventorySlot.parse(encoded)
                boat = catalog.get_item_data(stack.item_id) if stack else None
                if (
                    stack
                    and stack.quantity > 0
                    and boat
                    and boat.get("ObjType") == BOAT_TYPE
                    and skills["navegacion"] >= required_navigation(boat, stats, skills)
                ):
                    navigation.update(
                        boat_slot=slot.removeprefix("slot_"), boat_item=str(stack.item_id)
                    )
                    break
            else:
                return Decision(
                    {
                        "applied": False,
                        "message": (
                            "Necesitas una embarcación válida y la habilidad "
                            "de Navegación requerida."
                        ),
                    },
                    {},
                )
        new_map, x, y = destination
        return Decision(
            {
                "applied": True,
                "navigation_changed": was_sailing != water,
                "sailing": water,
                "dead": int(stats.get("min_hp", 0)) <= 0,
            },
            {
                position_key: {
                    "map": str(new_map),
                    "x": str(x),
                    "y": str(y),
                    "heading": str(heading),
                },
                stats_key: navigation,
            },
        )

    return await transact(
        player.redis.redis,
        player_action_resources(user),
        identity,
        {
            "transfer": user,
            "origin": list(origin),
            "destination": list(destination),
            "heading": heading,
        },
        decide,
    )
