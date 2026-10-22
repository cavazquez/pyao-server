"""NPC administrativos: creación con reservas, retirada y cambios persistentes."""

import json
import time
from typing import TYPE_CHECKING, cast

from src.economy.merchant_stock import catalog_key, stock_policy
from src.services.classic_chat.admin_character import warp
from src.services.classic_chat.admin_common import audited, fields
from src.services.classic_chat.context import ChatCommandError, ChatContext, integer
from src.utils.gold_atomic import operation_id
from src.utils.redis_config import RedisKeys
from src.utils.resource_transaction import Decision, Resource, Snapshot

AREA_RADIUS = 10
MAX_DIALOG_LENGTH = 400
POSITION_COMPONENTS = 3

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from src.models.npc import NPC

PRETORIAN_IDS = tuple(range(900, 924, 2))
MAX_ADMIN_NPCS_PER_MAP = 512


def require_spawned(npc: NPC | None) -> NPC:
    """Exige una instancia registrada antes de continuar una creación de grupo.

    Returns:
        NPC creado y registrado en el mundo.

    Raises:
        ChatCommandError: Si no se pudo crear el NPC en su casilla reservada.
    """
    if npc is None:
        message = "No se pudo crear el NPC en la casilla reservada."
        raise ChatCommandError(message)
    return npc


def free_positions(
    ctx: ChatContext, map_id: int, x: int, y: int, count: int
) -> list[tuple[int, int]]:
    """Busca casillas sin ocupar, reservadas después sin ceder el event loop.

    Returns:
        Una casilla por criatura, sin duplicados.

    Raises:
        ChatCommandError: Si falta espacio.
    """
    positions = []
    for radius in range(1, 10):
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                if max(abs(dx), abs(dy)) == radius and ctx.deps.map_manager.can_move_to(
                    map_id, x + dx, y + dy
                ):
                    positions.append((x + dx, y + dy))
                    if len(positions) == count:
                        return positions
    message = "No hay suficientes casillas libres."
    raise ChatCommandError(message)


async def spawn(ctx: ChatContext) -> None:
    """Crea una instancia administrativa con o sin reaparición.

    Raises:
        ChatCommandError: Si los datos o precondiciones de la operación son inválidos.
    """
    identifier = integer(ctx.arguments, 1, 899)
    if ctx.deps.npc_catalog.get_npc_data(identifier) is None:
        message = "El NPC no existe en el catálogo."
        raise ChatCommandError(message)
    position = await ctx.position()
    if len(ctx.deps.map_manager.get_npcs_in_map(position["map"])) >= MAX_ADMIN_NPCS_PER_MAP:
        message = "Se alcanzó el límite de NPC administrativos del mapa."
        raise ChatCommandError(message)
    await audited(
        ctx,
        (),
        {"spawn_npc": identifier, "map": position["map"]},
        lambda _snapshot: Decision({"applied": True}, {}),
    )
    locations = free_positions(ctx, position["map"], position["x"], position["y"], 1)
    reservation = operation_id()
    ctx.deps.map_manager.reserve_positions(reservation, position["map"], locations)
    try:
        template = ctx.deps.npc_catalog.get_npc_data(identifier) or {}
        respawn = (
            max(60, int(str(template.get("respawn_time", 0)))) if ctx.command == "/RACC" else 0
        )
        npc = await ctx.deps.npc_service.spawn_npc(
            identifier,
            position["map"],
            *locations[0],
            reservation=reservation,
            respawn_seconds=respawn,
        )
        if npc is None:
            message = "No se pudo crear el NPC."
            raise ChatCommandError(message)
        await ctx.tell(f"Creado {npc.name}, instancia {npc.char_index}.")
    finally:
        ctx.deps.map_manager.release_positions(reservation)


async def remove(ctx: ChatContext) -> None:
    """Retira sin botín ni XP; /RMATA programa la reaparición del NPC original."""
    if ctx.command == "/MASSKILL":
        position = await ctx.position()
        targets = [
            npc
            for npc in ctx.deps.map_manager.get_npcs_in_map(position["map"])
            if max(abs(npc.x - position["x"]), abs(npc.y - position["y"])) <= AREA_RADIUS
        ]
    else:
        targets = [await ctx.npc()]
    await audited(
        ctx,
        (),
        {"remove_npcs": [npc.instance_id for npc in targets]},
        lambda _snapshot: Decision({"applied": True}, {}),
    )
    for npc in targets:
        ctx.deps.npc_respawn_service.cancel_respawn(npc.instance_id)
        await ctx.deps.npc_service.remove_npc(npc)
        if ctx.command == "/RMATA":
            await ctx.deps.npc_respawn_service.schedule_respawn(npc)
    await ctx.tell(f"Retirados {len(targets)} NPC sin entregar recompensas.")


async def dialog(ctx: ChatContext) -> None:
    """Cambia el diálogo que leen los jugadores al seleccionar esta instancia.

    Raises:
        ChatCommandError: Si los datos o precondiciones de la operación son inválidos.
    """
    npc = await ctx.npc()
    if len(ctx.arguments) > MAX_DIALOG_LENGTH:
        message = "El diálogo no puede superar 400 caracteres."
        raise ChatCommandError(message)
    await fields(ctx, RedisKeys.npc_instance(npc.instance_id), {"description": ctx.arguments})
    npc.description = ctx.arguments
    await ctx.tell("Diálogo actualizado.")


async def reset_inventory(ctx: ChatContext) -> None:
    """Repone explícitamente desde la política de Redis, sin volver a leer el TOML.

    Raises:
        ChatCommandError: Si los datos o precondiciones de la operación son inválidos.
    """
    npc = await ctx.npc()
    if not npc.is_merchant:
        message = "El NPC seleccionado no tiene inventario comercial."
        raise ChatCommandError(message)
    key, policy, index = (
        RedisKeys.merchant_inventory(npc.npc_id),
        catalog_key(npc.npc_id),
        f"merchant:{npc.npc_id}:items",
    )

    def decide(snapshot: Snapshot) -> Decision:
        state = cast("dict[str, str]", snapshot[policy])
        rows, _interval, _last = stock_policy(state)
        stock = {
            f"slot_{slot}": f"{item}:{maximum}" if maximum else ""
            for slot, (item, maximum, _step) in enumerate(rows, 1)
        }
        return Decision(
            {"applied": True},
            {
                key: stock,
                policy: {"last_restock": str(int(time.time()))},
                index: {str(row[0]) for row in rows},
            },
        )

    await audited(
        ctx,
        (Resource(key, "hash", replace=True), Resource(policy, "hash"), Resource(index, "set")),
        {"reset_merchant": npc.npc_id},
        decide,
    )
    await ctx.tell("Inventario del mercader repuesto desde su política persistida en Redis.")


async def follow(ctx: ChatContext) -> None:
    """Alterna seguimiento administrativo, sin convertir una criatura en mascota."""
    npc = await ctx.npc()
    following = 0 if npc.gm_follow_user == ctx.user else ctx.user
    await fields(
        ctx,
        RedisKeys.npc_instance(npc.instance_id),
        {"gm_follow_user": str(following), "paralyzed_until": "0"},
    )
    npc.gm_follow_user, npc.paralyzed_until = following, 0.0
    await ctx.tell("El NPC te sigue." if following else "El NPC dejó de seguirte.")


async def mimic(ctx: ChatContext) -> None:
    """Aplica apariencia canónica; /IMPERSONAR además ocupa el lugar del NPC."""
    npc = await ctx.npc()
    await fields(
        ctx,
        ctx.key,
        {
            "morphed_body": str(npc.body_id),
            "morphed_head": str(npc.head_id),
            "morphed_until": str(time.time() + 86400),
        },
    )
    if ctx.command == "/IMPERSONAR":
        ctx.deps.npc_respawn_service.cancel_respawn(npc.instance_id)
        await ctx.deps.npc_service.remove_npc(npc)
        await warp(ctx, "YO", npc.map_id, npc.x, npc.y)
    if ctx.deps.player_death_service:
        await ctx.deps.player_death_service.publish_state(ctx.user)
    await ctx.tell(f"Has adoptado la apariencia de {npc.name}.")


async def pretorians(ctx: ChatContext) -> None:
    """Crea un grupo de plantillas reales o retira el grupo existente en un mapa.

    Raises:
        ChatCommandError: Si los datos o precondiciones de la operación son inválidos.
    """
    parts = ctx.arguments.replace(",", " ").split()
    position = await ctx.position()
    map_id = integer(parts[0], 1, 290) if parts else position["map"]
    if not ctx.deps.map_manager.has_map(map_id):
        message = "Mapa desconocido."
        raise ChatCommandError(message)
    key = f"world:pretorians:{map_id}"
    if ctx.command == "/ELIMINARPRETORIANOS":
        await fields(ctx, key, {"active": "0"})
        targets = [
            npc for npc in ctx.deps.map_manager.get_npcs_in_map(map_id) if npc.role == "pretorian"
        ]
        for member in targets:
            ctx.deps.npc_respawn_service.cancel_respawn(member.instance_id)
            await ctx.deps.npc_service.remove_npc(member)
        await ctx.tell(f"Retirados {len(targets)} pretorianos del mapa {map_id}.")
        return
    if len(parts) != POSITION_COMPONENTS:
        message = "Uso: /CREARPRETORIANOS mapa x y"
        raise ChatCommandError(message)
    x, y = integer(parts[1], 1, 100), integer(parts[2], 1, 100)
    if any(ctx.deps.npc_catalog.get_npc_data(value) is None for value in PRETORIAN_IDS):
        message = "El catálogo de pretorianos está incompleto."
        raise ChatCommandError(message)
    reservation = operation_id()
    locations = free_positions(ctx, map_id, x, y, len(PRETORIAN_IDS))
    ctx.deps.map_manager.reserve_positions(reservation, map_id, locations)
    created: list[NPC] = []
    claimed = False

    def decide(snapshot: Snapshot) -> Decision:
        state = cast("dict[str, str]", snapshot[key])
        if state.get("active") == "1":
            return Decision(
                {"applied": False, "message": "Ya hay un grupo pretoriano en ese mapa."}, {}
            )
        return Decision({"applied": True}, {key: {"active": "1", "reservation": reservation}})

    try:
        await audited(ctx, (Resource(key, "hash"),), {"pretorians": map_id}, decide)
        claimed = True
        for identifier, (px, py) in zip(PRETORIAN_IDS, locations, strict=True):
            npc = require_spawned(
                await ctx.deps.npc_service.spawn_npc(
                    identifier,
                    map_id,
                    px,
                    py,
                    reservation=reservation,
                    role="pretorian",
                    respawn_seconds=0,
                )
            )
            created.append(npc)
        await fields(ctx, key, {"instances": json.dumps([npc.instance_id for npc in created])})
        await ctx.tell(f"Grupo pretoriano creado: {len(created)} NPC en mapa {map_id}.")
    except BaseException:
        for npc in created:
            await ctx.deps.npc_service.remove_npc(npc)
        if claimed:
            await ctx.redis.hset(key, "active", "0")
        raise
    finally:
        ctx.deps.map_manager.release_positions(reservation)


HANDLERS: dict[str, Callable[[ChatContext], Awaitable[None]]] = {
    "/ACC": spawn,
    "/RACC": spawn,
    "/MATA": remove,
    "/RMATA": remove,
    "/MASSKILL": remove,
    "/SETDIALOG": dialog,
    "/SEGUIR": follow,
    "/IMPERSONAR": mimic,
    "/MIMETIZAR": mimic,
    "/RESETINV": reset_inventory,
    "/CREARPRETORIANOS": pretorians,
    "/ELIMINARPRETORIANOS": pretorians,
}
