"""Movimientos y cambios GM de personajes usando el ciclo de vida compartido."""

import json
import time
from typing import TYPE_CHECKING, cast

from src.command_handlers.gm_command_handler import GMCommandHandler
from src.commands.gm_command import GMCommand
from src.models.item_constants import MAX_PLAYER_GOLD
from src.services.classic_chat.admin_common import audited
from src.services.classic_chat.admin_edit import EXTENDED_FIELDS, edit
from src.services.classic_chat.context import ChatCommandError, ChatContext, integer
from src.services.player.lifecycle import hp_changes
from src.services.player_progression import advance_player_level, publish_progress
from src.utils.gold_atomic import operation_id
from src.utils.redis_config import RedisKeys
from src.utils.resource_transaction import Decision, Resource, Snapshot

TELEPORT_FULL_ARGUMENTS = 4
TRIPLE_ARGUMENTS = 3

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

MAX_DESCRIPTION = 255


async def warp(ctx: ChatContext, username: str, map_id: int, x: int, y: int) -> None:
    """Usa la transición nativa con reservas y permisos, también para otros usuarios.

    Raises:
        ChatCommandError: Si los datos o precondiciones de la operación son inválidos.
    """
    result = await GMCommandHandler(
        ctx.deps.player_repo,
        ctx.deps.account_repo,
        ctx.deps.player_map_service,
        ctx.sender,
        ctx.deps.action_cadence,
    ).handle(GMCommand(ctx.user, 11, username, map_id, x, y))
    if not result.success:
        message = result.error_message or "No se pudo teletransportar."
        raise ChatCommandError(message)


def nearby(ctx: ChatContext, map_id: int, x: int, y: int) -> tuple[int, int]:
    """Busca una casilla libre cercana sin superponer actores.

    Returns:
        Coordenadas libres validadas por el mapa.

    Raises:
        ChatCommandError: Si los datos o precondiciones de la operación son inválidos.
    """
    for radius in range(1, 5):
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                if max(abs(dx), abs(dy)) == radius and ctx.deps.map_manager.can_move_to(
                    map_id, x + dx, y + dy
                ):
                    return x + dx, y + dy
    message = "No hay una casilla libre junto al destino."
    raise ChatCommandError(message)


async def teleport(ctx: ChatContext) -> None:
    """Completa /TELEP, /IRA, /SUM, /IRCERCA y /TELEPLOC.

    Raises:
        ChatCommandError: Si los datos o precondiciones de la operación son inválidos.
    """
    parts = ctx.arguments.split()
    if ctx.command == "/TELEP":
        if len(parts) == TRIPLE_ARGUMENTS:
            parts.insert(0, "YO")
        if len(parts) != TELEPORT_FULL_ARGUMENTS:
            message = "Uso: /TELEP [nombre|YO] mapa x y"
            raise ChatCommandError(message)
        await warp(
            ctx,
            parts[0],
            integer(parts[1], 1, 32767),
            integer(parts[2], 1, 100),
            integer(parts[3], 1, 100),
        )
    elif ctx.command == "/TELEPLOC":
        selection = await ctx.read_hash(f"chat:target:{ctx.user}")
        position = await ctx.position()
        if int(selection.get("map", 0)) != position["map"]:
            message = "Selecciona una casilla del mapa actual."
            raise ChatCommandError(message)
        await warp(
            ctx,
            "YO",
            position["map"],
            integer(selection.get("x", "0"), 1, 100),
            integer(selection.get("y", "0"), 1, 100),
        )
    elif ctx.command == "/SUM":
        account = await ctx.account(ctx.arguments)
        own = await ctx.position()
        x, y = nearby(ctx, own["map"], own["x"], own["y"])
        await warp(ctx, account["username"], own["map"], x, y)
    else:
        account = await ctx.account(ctx.arguments)
        target = await ctx.deps.player_repo.get_position(int(account["user_id"]))
        if not target:
            message = "El jugador no tiene una posición disponible."
            raise ChatCommandError(message)
        x, y = nearby(ctx, target["map"], target["x"], target["y"])
        await warp(ctx, "YO", target["map"], x, y)
    await ctx.tell("Teletransporte completado.")


async def modify(ctx: ChatContext) -> None:
    """Modifica campos explícitos y registra auditoría sin aceptar nombres de claves.

    Raises:
        ChatCommandError: Si los datos o precondiciones de la operación son inválidos.
    """
    parts = ctx.arguments.split(maxsplit=2)
    if len(parts) != TRIPLE_ARGUMENTS:
        message = "Uso: /MOD nombre atributo valor"
        raise ChatCommandError(message)
    account = await ctx.account(parts[0])
    user, field = int(account["user_id"]), parts[1].lower()
    field = "level" if field == "nivel" else field
    if field in EXTENDED_FIELDS:
        await edit(ctx, parts[0], field, parts[2])
        return
    allowed = {
        "vida": "min_hp",
        "hp": "min_hp",
        "mana": "min_mana",
        "energia": "min_sta",
        "oro": "gold",
        "exp": "experience",
        "nivel": "level",
        "criminal": "criminal",
    }
    if field not in allowed:
        message = "Atributos: vida, mana, energia, oro, exp, nivel, criminal."
        raise ChatCommandError(message)
    field = allowed[field]
    value = integer(
        parts[2],
        1 if field == "level" else 0,
        100 if field == "level" else 1 if field == "criminal" else MAX_PLAYER_GOLD,
    )
    key, position_key = RedisKeys.player_user_stats(user), RedisKeys.player_position(user)
    audit = f"moderation:change:{operation_id()}"

    def decide(snapshot: Snapshot) -> Decision:
        before = cast("dict[str, str]", snapshot[key])
        position = cast("dict[str, str]", snapshot[position_key])
        if not before:
            return Decision({"applied": False, "message": "El personaje no existe."}, {})
        maximum = {"min_hp": "max_hp", "min_mana": "max_mana", "min_sta": "max_sta"}.get(field)
        if maximum and value > int(before.get(maximum, 0)):
            return Decision(
                {"applied": False, "message": "El valor supera el máximo del personaje."}, {}
            )
        if field == "min_hp" and value > 0 and int(before.get("min_hp", 0)) <= 0:
            return Decision(
                {"applied": False, "message": "Usa /REVIVIR antes de editar la vida de un muerto."},
                {},
            )
        changes = (
            hp_changes(before, position, value, audit) if field == "min_hp" else {field: str(value)}
        )
        return Decision(
            {"applied": True, "message": "Personaje actualizado."},
            {
                key: changes,
                audit: json.dumps(
                    {
                        "actor": ctx.user,
                        "target": user,
                        "field": field,
                        "value": value,
                        "at": int(time.time()),
                    }
                ),
            },
        )

    result = await ctx.commit(
        (Resource(key, "hash"), Resource(position_key, "hash"), Resource(audit, "string")),
        {"target": user, "field": field, "value": value},
        decide,
    )
    if result["applied"] and ctx.deps.player_death_service:
        if field == "min_hp" and value == 0:
            await ctx.deps.player_death_service.handle_player_death(user, "administración")
        await ctx.deps.player_death_service.publish_state(user)
    if result["applied"] and field == "experience":
        sender = ctx.deps.map_manager.get_player_message_sender(user)
        if sender:
            await advance_player_level(ctx.deps.player_repo, user, sender)
            await publish_progress(ctx.deps.player_repo, user, sender)
    await ctx.tell(result["message"])


async def set_description(ctx: ChatContext) -> None:
    """Actualiza la descripción de un objetivo existente.

    Raises:
        ChatCommandError: Si los datos o precondiciones de la operación son inválidos.
    """
    parts = ctx.arguments.split("@", 1) if "@" in ctx.arguments else ctx.arguments.split(maxsplit=1)
    if not parts:
        message = "Uso: /SETDESC nombre@descripción"
        raise ChatCommandError(message)
    account = await ctx.account(parts[0])
    text = parts[1] if len(parts) > 1 else ""
    if len(text) > MAX_DESCRIPTION:
        message = "La descripción no puede superar 255 caracteres."
        raise ChatCommandError(message)
    key = RedisKeys.player_user_stats(int(account["user_id"]))
    result = await ctx.commit(
        (Resource(key, "hash"),),
        {"target": account["user_id"]},
        lambda _snapshot: Decision(
            {"applied": True, "message": "Descripción actualizada."}, {key: {"description": text}}
        ),
    )
    await ctx.tell(result["message"])


async def status(ctx: ChatContext) -> None:
    """Aplica estados autoritativos de criminalidad o confusión a otro personaje."""
    account = await ctx.account(ctx.arguments)
    user = int(account["user_id"])
    key = RedisKeys.player_user_stats(user)
    field = "criminal" if ctx.command in {"/PERDON", "/CONDEN"} else "dumb_until"
    value = (
        "1"
        if ctx.command == "/CONDEN"
        else str(time.time() + 86400)
        if ctx.command == "/ESTUPIDO"
        else "0"
    )
    result = await ctx.commit(
        (Resource(key, "hash"),),
        {"target": user, "field": field},
        lambda _snapshot: Decision(
            {"applied": True, "message": "Estado actualizado."}, {key: {field: value}}
        ),
    )
    sender = ctx.deps.map_manager.get_player_message_sender(user)
    if result["applied"] and sender:
        await sender.status_effects.sync_status(user, ctx.deps.player_repo)
    await ctx.tell(result["message"])


async def execute_or_revive(ctx: ChatContext) -> None:
    """Mata o resucita utilizando los mismos commits y publicación del combate.

    Raises:
        ChatCommandError: Si los datos o precondiciones de la operación son inválidos.
    """
    account = await ctx.account(ctx.arguments)
    user = int(account["user_id"])
    service = ctx.deps.player_death_service
    if service is None:
        message = "El ciclo de vida no está disponible."
        raise ChatCommandError(message)
    sender = ctx.deps.map_manager.get_player_message_sender(user)
    if ctx.command == "/REVIVIR":
        if sender is None:
            message = "El jugador debe estar conectado."
            raise ChatCommandError(message)
        await service.revive_player(user, sender)
        return
    key, position_key = RedisKeys.player_user_stats(user), RedisKeys.player_position(user)
    event = operation_id()

    def decide(snapshot: Snapshot) -> Decision:
        before = cast("dict[str, str]", snapshot[key])
        position = cast("dict[str, str]", snapshot[position_key])
        return Decision(
            {"applied": True, "message": "Ejecución confirmada."},
            {key: hp_changes(before, position, 0, event)},
        )

    result = await ctx.commit(
        (Resource(key, "hash"), Resource(position_key, "hash")), {"target": user}, decide
    )
    if result["applied"]:
        await service.handle_player_death(user, "administración")
    await ctx.tell(result["message"])


async def invisible(ctx: ChatContext) -> None:
    """Alterna invisibilidad GM y la sincroniza a todos los observadores."""

    def decide(snapshot: Snapshot) -> Decision:
        before = cast("dict[str, str]", snapshot[ctx.key])
        active = float(before.get("invisible_until", 0)) > time.time()
        return Decision(
            {
                "applied": True,
                "message": "Ahora eres visible." if active else "Ahora eres invisible.",
            },
            {ctx.key: {"invisible_until": "0" if active else str(time.time() + 86400)}},
        )

    result = await ctx.commit((Resource(ctx.key, "hash"),), {}, decide)
    if result["applied"]:
        await ctx.sender.status_effects.sync_visibility(
            ctx.user, ctx.deps.player_repo, ctx.deps.map_manager
        )
    await ctx.tell(result["message"])


async def kick(ctx: ChatContext) -> None:
    """Cierra la conexión del jugador exacto sin alterar su cuenta ni su partida.

    Raises:
        ChatCommandError: Si los datos o precondiciones de la operación son inválidos.
    """
    account = await ctx.account(ctx.arguments)
    sender = ctx.deps.map_manager.get_player_message_sender(int(account["user_id"]))
    if sender is None:
        message = "El jugador no está conectado."
        raise ChatCommandError(message)
    await sender.send_console_msg("Has sido desconectado por un administrador.")
    await sender.connection.flush()
    sender.connection.close()
    await ctx.tell("Jugador desconectado.")


async def navigate_gm(ctx: ChatContext) -> None:
    """Alterna navegación administrativa sin crear barcos ni alterar habilidades."""
    account = await ctx.deps.account_repo.get_account_by_user_id(ctx.user) or {}
    account_key = RedisKeys.account_data(account["username"])

    def decide(snapshot: Snapshot) -> Decision:
        stats = cast("dict[str, str]", snapshot[ctx.key])
        active = stats.get("sailing") != "1"
        if int(stats.get("min_hp", 0)) <= 0:
            return Decision({"applied": False, "message": "Debes estar vivo para navegar."}, {})
        return Decision(
            {"applied": True},
            {
                ctx.key: {
                    "sailing": "1" if active else "0",
                    "gm_navigation_account": account_key if active else "",
                }
            },
        )

    await audited(ctx, (Resource(ctx.key, "hash"),), {"navigation": True}, decide)
    if ctx.deps.player_death_service:
        await ctx.deps.player_death_service.publish_state(ctx.user)
    await ctx.sender.send_navigate_toggle()
    await ctx.tell("Modo de navegación actualizado.")


HANDLERS: dict[str, Callable[[ChatContext], Awaitable[None]]] = {
    **dict.fromkeys(("/TELEP", "/TELEPLOC", "/IRA", "/SUM", "/IRCERCA"), teleport),
    **dict.fromkeys(("/PERDON", "/CONDEN", "/ESTUPIDO", "/NOESTUPIDO"), status),
    "/MOD": modify,
    "/SETDESC": set_description,
    "/EJECUTAR": execute_or_revive,
    "/REVIVIR": execute_or_revive,
    "/INVISIBLE": invisible,
    "/ECHAR": kick,
    "/NAVE": navigate_gm,
}
