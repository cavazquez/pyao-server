"""Diálogos clásicos de nobles y recompensas con el inventario transaccional."""

import json
from functools import lru_cache
from typing import TYPE_CHECKING, Any, cast

from src.models.items_catalog import ITEMS_CATALOG
from src.runtime_paths import data_dir
from src.services.classic_chat.admin_common import fields
from src.services.classic_chat.context import ChatCommandError, ChatContext, integer
from src.services.inventory_notifications import notify_inventory
from src.services.player_progression import advance_player_level, publish_progress
from src.utils.durability import require_durable
from src.utils.gold_atomic import operation_id
from src.utils.redis_config import RedisKeys
from src.utils.resource_transaction import Decision, Resource, Snapshot
from src.utils.slot_plan import SlotPlan

ARMOR_ARGUMENTS = 2
NOBLE_RANGE = 4

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from src.models.npc import NPC


@lru_cache(maxsize=1)
def service_catalog() -> dict[str, Any]:
    """Carga tipos de servicio por ID y nombre verificados.

    Returns:
        Metadatos clásicos, incluidas las excepciones de plantillas propias.
    """
    return cast(
        "dict[str, Any]",
        json.loads((data_dir() / "world/classic_services.json").read_text())["npcs"],
    )


@lru_cache(maxsize=1)
def reward_catalog() -> dict[str, Any]:
    """Carga las tablas del original, sin depender de los fuentes VB6 en ejecución.

    Returns:
        Umbrales, experiencia y armaduras por clase y tamaño.
    """
    return cast(
        "dict[str, Any]",
        json.loads((data_dir() / "world/classic_faction_rewards.json").read_text()),
    )


def npc_service(npc: NPC, kind: str) -> dict[str, Any]:
    """Comprueba la identidad de la plantilla antes de asignarle un servicio.

    Returns:
        Servicio de la plantilla reconocida.

    Raises:
        ChatCommandError: Si el NPC no ofrece ese servicio.
    """
    row = service_catalog().get(str(npc.npc_id), {})
    if row.get("name", "").casefold() != npc.name.casefold() or row.get("service") != kind:
        message = f"Selecciona un NPC del servicio {kind}."
        raise ChatCommandError(message)
    return cast("dict[str, Any]", row)


async def faction(ctx: ChatContext) -> None:
    """Enlista, consulta progreso o retira a un personaje de su facción.

    Raises:
        ChatCommandError: Si los datos o precondiciones de la operación son inválidos.
    """
    await ctx.alive()
    state = ctx.deps.world_state
    if state is None:
        message = "El servicio de facciones no está disponible."
        raise ChatCommandError(message)
    if ctx.command == "/RETIRARFACCION":
        result = await state.expansion.factions.command(ctx.user, "leave", {}, operation_id())
    else:
        npc = await ctx.npc()
        row = npc_service(npc, "noble")
        position = await ctx.position()
        if max(abs(npc.x - position["x"]), abs(npc.y - position["y"])) > NOBLE_RANGE:
            message = "Debes acercarte más al noble."
            raise ChatCommandError(message)
        if ctx.command == "/ENLISTAR":
            result = await state.expansion.factions.command(
                ctx.user, "join", {"faction": row["faction"]}, operation_id(), noble=npc
            )
        else:
            stats = await ctx.stats()
            if stats.get("faction_id") != row["faction"]:
                message = "No perteneces a las tropas de este noble."
                raise ChatCommandError(message)
            rank = int(stats.get(f"faction_reward_{row['faction']}", 0))
            thresholds = reward_catalog()["thresholds"][row["faction"]]
            field = "criminal_kills" if row["faction"] == "royal" else "citizen_kills"
            kills = max(0, int(stats.get(field, 0)) - int(stats.get("faction_kill_baseline", 0)))
            if ctx.command == "/INFORMACION":
                await ctx.tell(
                    "Ya recibiste todas las recompensas."
                    if rank >= len(thresholds)
                    else (
                        f"Bajas de facción: {kills}; próxima recompensa: {thresholds[rank]}; "
                        f"faltan {max(0, thresholds[rank] - kills)}."
                    )
                )
                return
            await reward(ctx, row["faction"], npc)
            return
    await require_durable(ctx.redis)
    await ctx.tell(result["message"])


async def reward(ctx: ChatContext, alignment: str, npc: NPC) -> None:
    """Entrega armaduras/experiencia una sola vez por rango y sin pérdida por espacio.

    Raises:
        ChatCommandError: Si los datos o precondiciones de la operación son inválidos.
    """
    account = await ctx.deps.account_repo.get_account_by_user_id(ctx.user) or {}
    data = reward_catalog()
    class_id = str(int(account.get("char_job", 1)))
    size = "bajo" if int(account.get("char_race", 1)) in {4, 5} else "alto"
    armors = data["armors"][class_id][alignment][size]
    if not all(ctx.deps.item_catalog.item_exists(item) for item in armors):
        message = "Las armaduras de la recompensa no existen en el catálogo."
        raise ChatCommandError(message)
    inventory = RedisKeys.player_inventory(ctx.user)
    counter = f"faction_reward_{alignment}"
    armor_policy = f"faction:armor:{alignment}"
    account_key = RedisKeys.account_data(account["username"])

    def decide(snapshot: Snapshot) -> Decision:
        stats = cast("dict[str, str]", snapshot[ctx.key])
        profile = cast("dict[str, str]", snapshot[account_key])
        if (
            profile.get("char_job") != account.get("char_job")
            or profile.get("char_race") != account.get("char_race")
            or int(stats.get("min_hp", 0)) <= 0
        ):
            return Decision(
                {"applied": False, "message": "El personaje cambió; vuelve a pedir la recompensa."},
                {},
            )
        index = int(stats.get(counter, 0))
        thresholds = data["thresholds"][alignment]
        if index >= len(thresholds):
            return Decision(
                {"applied": False, "message": "Ya recibiste todas las recompensas."}, {}
            )
        field = "criminal_kills" if alignment == "royal" else "citizen_kills"
        kills = max(0, int(stats.get(field, 0)) - int(stats.get("faction_kill_baseline", 0)))
        if (
            stats.get("faction_id") != alignment
            or kills < thresholds[index]
            or int(stats.get("level", 1)) < data["minimum_levels"][alignment][index]
        ):
            return Decision(
                {
                    "applied": False,
                    "message": "Todavía no alcanzaste las bajas o el nivel requeridos.",
                },
                {},
            )
        rank = index + 2
        quantities = [
            max(1, round(20 / (rank + 1))),
            max(1, round(rank * 2 / max(rank - 4, 1))),
            max(1, round(rank * 135 / 100)),
        ]
        bag = SlotPlan(
            cast("dict[str, str]", snapshot[inventory]),
            30,
            ctx.deps.inventory_repo.stacking.max_stack,
        )
        try:
            policy = cast("dict[str, str]", snapshot[armor_policy])
            effective = [
                int(
                    policy.get(
                        "4" if class_id in {"1", "6", "7"} and slot == 1 else str(slot), item
                    )
                )
                for slot, item in enumerate(armors, 1)
            ]
            for item, count in zip(effective, quantities, strict=True):
                bag.give(item, count)
        except ValueError:
            return Decision(
                {
                    "applied": False,
                    "message": "Libera espacio en tu inventario antes de reclamar la recompensa.",
                },
                {},
            )
        experience = int(data["experience"][index + 1])
        changes = {
            counter: str(index + 1),
            "experience": str(int(stats.get("experience", 0)) + experience),
        }
        return Decision(
            {"applied": True, "message": "Recompensa entregada.", "experience": experience},
            {ctx.key: changes, inventory: bag.fields()},
        )

    result = await ctx.commit_near(
        npc,
        (
            Resource(ctx.key, "hash"),
            Resource(inventory, "hash"),
            Resource(armor_policy, "hash"),
            Resource(account_key, "hash"),
        ),
        {"alignment": alignment},
        decide,
        distance=4,
    )
    if result["applied"]:
        await notify_inventory(ctx.sender, ctx.deps.inventory_repo, ctx.user)
        await advance_player_level(ctx.deps.player_repo, ctx.user, ctx.sender)
        await publish_progress(ctx.deps.player_repo, ctx.user, ctx.sender)
    await ctx.tell(result["message"])


async def faction_armor(ctx: ChatContext) -> None:
    """Configura una armadura de recompensa, como ImperialArmour/ChaosArmour.

    Raises:
        ChatCommandError: Si los datos o precondiciones de la operación son inválidos.
    """
    parts = ctx.arguments.split()
    if len(parts) != ARMOR_ARGUMENTS:
        message = f"Uso: {ctx.command} índice(1 a 4) objeto"
        raise ChatCommandError(message)
    slot, item_id = integer(parts[0], 1, 4), integer(parts[1], 1, 32767)
    item = ITEMS_CATALOG.get(item_id)
    if item is None or item.item_type.value != "armor":
        message = "El objeto debe ser una armadura válida del catálogo."
        raise ChatCommandError(message)
    alignment = "royal" if ctx.command == "/AI" else "chaos"
    await fields(ctx, f"faction:armor:{alignment}", {str(slot): str(item_id)})
    await ctx.tell("Armadura de recompensa de facción actualizada; no se entregaron objetos.")


HANDLERS: dict[str, Callable[[ChatContext], Awaitable[None]]] = {
    "/ENLISTAR": faction,
    "/RETIRARFACCION": faction,
    "/INFORMACION": faction,
    "/RECOMPENSA": faction,
    "/AI": faction_armor,
    "/AC": faction_armor,
}
