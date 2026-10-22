"""Panel textual, colas de asistencia y preferencias reales de Game Master."""

import json
import time
from operator import itemgetter
from typing import TYPE_CHECKING, cast

from src.services.classic_chat.admin_common import audited, fields
from src.services.classic_chat.appearance import refresh_nameplate
from src.services.classic_chat.context import ChatCommandError, ChatContext, integer
from src.utils.redis_config import RedisKeys
from src.utils.resource_transaction import Decision, Resource, Snapshot

MAX_COMMENT_LENGTH = 400

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

PAGE_SIZE = 15


async def show(ctx: ChatContext) -> None:
    """Reemplaza formularios Win32 por vistas paginadas utilizables desde Godot.

    Raises:
        ChatCommandError: Si los datos o precondiciones de la operación son inválidos.
    """
    args = ctx.arguments.upper().split()
    mode = args[0] if args else "SOS"
    page = integer(args[1], 1, 10000) if len(args) > 1 else 1
    if mode == "SERVER" or ctx.command == "/PANELGM":
        players = ctx.deps.map_manager.get_all_online_players()
        await ctx.tell(
            f"Panel GM: {len(players)} jugadores; {len(ctx.deps.map_manager.get_all_npcs())} NPC.\n"
            "/SHOW SOS [página] | /SHOW DENUNCIAS [página]\n"
            "/INFO nombre | /TELEP [nombre|YO] mapa x y\n"
            "/HABILITAR | /DOBACKUP | /APAGAR | /AYUDA página"
        )
        return
    modes = {"SOS": "help", "DENUNCIAS": "denounce", "BUGS": "bug", "ROL": "role"}
    if mode not in modes:
        message = "Uso: /SHOW SOS|DENUNCIAS|BUGS|ROL|SERVER [página]"
        raise ChatCommandError(message)
    reports = await ctx.read_hash(f"chat:reports:{modes[mode]}")
    rows = sorted((json.loads(value) for value in reports.values()), key=itemgetter("at"))
    pages = max(1, (len(rows) + PAGE_SIZE - 1) // PAGE_SIZE)
    if page > pages:
        message = "Esa página no existe."
        raise ChatCommandError(message)
    lines = [f"{mode}: {len(rows)} solicitudes ({page}/{pages})."]
    for row in rows[(page - 1) * PAGE_SIZE : page * PAGE_SIZE]:
        account = await ctx.deps.account_repo.get_account_by_user_id(int(row["user"])) or {}
        lines.append(f"{account.get('username', row['user'])}: {row['text']}")
    await ctx.tell("\n".join(lines))


async def clear_sos(ctx: ChatContext) -> None:
    """Vacía sólo la cola SOS; conserva denuncias, bugs y auditoría.

    Raises:
        ChatCommandError: Si los datos o precondiciones de la operación son inválidos.
    """
    if ctx.arguments.upper() not in {"", "SOS"}:
        message = "Uso: /BORRAR SOS"
        raise ChatCommandError(message)
    key = "chat:reports:help"
    await audited(
        ctx,
        (Resource(key, "hash", deletable=True),),
        {"clear": "help"},
        lambda _snapshot: Decision({"applied": True}, {key: None}),
    )
    await ctx.tell("Solicitudes de asistencia eliminadas de la cola.")


async def comment(ctx: ChatContext) -> None:
    """Registra un comentario administrativo privado con actor y fecha.

    Raises:
        ChatCommandError: Si los datos o precondiciones de la operación son inválidos.
    """
    if not ctx.arguments or len(ctx.arguments) > MAX_COMMENT_LENGTH:
        message = "Uso: /REM comentario (hasta 400 caracteres)"
        raise ChatCommandError(message)
    key = f"moderation:comments:{ctx.user}"
    identifier = str(time.time_ns())
    await fields(ctx, key, {identifier: ctx.arguments})
    await ctx.tell("Comentario guardado en Redis.")


async def preference(ctx: ChatContext) -> None:
    """Alterna recepción de denuncias, chat de clan, etiqueta o agresión de NPC."""
    field, default = {
        "/DENUNCIAS": ("gm_denounces", "1"),
        "/SHOWCMSG": ("gm_clan_chat", "0"),
        "/SHOWNAME": ("show_name", "1"),
        "/IGNORADO": ("gm_targetable", "1"),
    }[ctx.command]

    def decide(snapshot: Snapshot) -> Decision:
        before = cast("dict[str, str]", snapshot[ctx.key])
        value = "0" if before.get(field, default) == "1" else "1"
        changes = {field: value}
        if field == "gm_targetable":
            changes["npc_ignore"] = "0" if value == "1" else "1"
        writes: dict[str, dict[str, str] | set[str]] = {ctx.key: changes}
        if field == "gm_clan_chat":
            observers = set(cast("set[str]", snapshot["chat:clan_observers"]))
            observers.discard(str(ctx.user))
            if value == "1":
                observers.add(str(ctx.user))
            writes["chat:clan_observers"] = observers
        return Decision({"applied": True, "enabled": value == "1"}, writes)

    resources = (Resource(ctx.key, "hash"),) + (
        (Resource("chat:clan_observers", "set"),) if field == "gm_clan_chat" else ()
    )
    result = await audited(ctx, resources, {"preference": field}, decide)
    if field == "show_name":
        await refresh_nameplate(ctx, ctx.user)
    await ctx.tell(f"{ctx.command}: {'activado' if result['enabled'] else 'desactivado'}.")


async def activity(ctx: ChatContext) -> None:
    """Consulta ocultación vigente o actividad de oficio confirmada recientemente."""
    users = ctx.deps.map_manager.get_all_online_players()
    if not users:
        await ctx.tell("No hay jugadores conectados.")
        return
    async with ctx.redis.pipeline(transaction=False) as pipe:
        for user, _name, _map in users:
            pipe.hmget(RedisKeys.player_user_stats(user), ["hidden_until", "work_last_at"])
        states = await pipe.execute()
    field = 0 if ctx.command == "/OCULTANDO" else 1
    names = [
        name
        for (_user, name, _map), state in zip(users, states, strict=True)
        if float(state[field] or 0) > (time.time() if field == 0 else time.time() - 5)
    ]
    await ctx.tell(f"{ctx.command}: " + (", ".join(names) or "ninguno"))


HANDLERS: dict[str, Callable[[ChatContext], Awaitable[None]]] = {
    "/SHOW": show,
    "/PANELGM": show,
    "/REM": comment,
    "/BORRAR": clear_sos,
    **dict.fromkeys(("/DENUNCIAS", "/SHOWCMSG", "/SHOWNAME", "/IGNORADO"), preference),
    "/TRABAJANDO": activity,
    "/OCULTANDO": activity,
}
