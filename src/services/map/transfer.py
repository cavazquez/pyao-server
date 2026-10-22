"""Confirma posición y navegación juntas, sobre el origen e inventario observados."""

import time
from typing import TYPE_CHECKING, Any, cast

from src.services.action_resources import player_action_resources
from src.services.classic_chat.world_rules import resources as world_resources
from src.services.classic_chat.world_rules import rules
from src.services.combat_snapshot import levels
from src.services.navigation import BOAT_TYPE, required_navigation
from src.utils.inventory_slot import InventorySlot
from src.utils.redis_config import RedisKeys
from src.utils.resource_transaction import Decision, Resource, Snapshot, transact

JAIL_MAP = 66
NEWBIE_LEVEL_LIMIT = 12

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
    *,
    home_deadline: float | None = None,
) -> dict[str, Any]:
    """Rechaza un origen cambiado o embarcación inválida sin escribir estado parcial.

    Returns:
        Confirmación y estado de navegación del mismo commit Redis.
    """
    position_key = RedisKeys.player_position(user)
    stats_key = RedisKeys.player_user_stats(user)
    gm_account = str(await player.redis.hget(stats_key, "gm_navigation_account") or "")

    def decide(snapshot: Snapshot) -> Decision:
        position = cast("dict[str, str]", snapshot[position_key])
        stats = cast("dict[str, str]", snapshot[stats_key])
        actual = tuple(int(position.get(key, 0)) for key in ("map", "x", "y"))
        if actual != origin:
            return Decision({"applied": False, "message": "Tu posición ya cambió."}, {})
        if home_deadline is not None and (
            int(stats.get("min_hp", 0)) > 0
            or stats.get("death_state") != "complete"
            or stats.get("home_due", "0") != str(home_deadline)
            or home_deadline > time.time()
        ):
            return Decision(
                {"applied": False, "message": "El regreso al hogar se canceló o la vida cambió."},
                {},
            )
        if float(stats.get("jail_until", 0)) > time.time() and destination[0] != JAIL_MAP:
            return Decision(
                {
                    "applied": False,
                    "message": "Debes cumplir tu condena antes de salir de la cárcel.",
                },
                {},
            )
        policy = rules(snapshot, destination[0])
        restriction = policy.get("restriction", "NO")
        permitted = {
            "NO": True,
            "NEWBIE": int(stats.get("level", 1)) <= NEWBIE_LEVEL_LIMIT,
            "ARMADA": stats.get("faction_id") == "royal",
            "CAOS": stats.get("faction_id") == "chaos",
            "FACCION": stats.get("faction_id", "neutral") != "neutral",
        }
        if not permitted.get(restriction):
            return Decision(
                {"applied": False, "message": "No cumples la restricción de entrada del mapa."}, {}
            )
        navigation = {"sailing": "1" if water else "0"}
        if home_deadline is not None:
            navigation["home_due"] = "0"
        admin = cast("dict[str, str]", snapshot.get(gm_account) or {})
        gm_navigation = bool(
            gm_account
            and stats.get("gm_navigation_account") == gm_account
            and admin.get("is_gm") == "1"
            and admin.get("user_id") == str(user)
        )
        if water and not gm_navigation:
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
        return Decision(
            {
                "applied": True,
                "navigation_changed": (stats.get("sailing") == "1") != water,
                "sailing": water,
                "dead": int(stats.get("min_hp", 0)) <= 0,
            },
            {
                position_key: {
                    "map": str(destination[0]),
                    "x": str(destination[1]),
                    "y": str(destination[2]),
                    "heading": str(heading),
                },
                stats_key: navigation,
            },
        )

    return await transact(
        player.redis.redis,
        (
            *player_action_resources(user),
            *world_resources(destination[0]),
            *((Resource(gm_account, "hash"),) if gm_account else ()),
        ),
        identity,
        {
            "transfer": user,
            "origin": list(origin),
            "destination": list(destination),
            "heading": heading,
            **({"home_deadline": home_deadline} if home_deadline is not None else {}),
        },
        decide,
    )
