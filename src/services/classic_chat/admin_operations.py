"""Operación del servidor con recargas validadas y cierre por el ciclo nativo."""

import asyncio
import json
import os
import stat
import time
from pathlib import Path
from typing import TYPE_CHECKING, cast

from src.config.config_manager import config_manager
from src.services.classic_chat.admin_common import audited, fields
from src.services.classic_chat.context import ChatCommandError, ChatContext
from src.utils.durability import require_durable
from src.utils.resource_transaction import Decision, Resource, Snapshot

KEY_ARGUMENTS = 2
MAX_CADENCE_SECONDS = 30
MAX_MOTD_LENGTH = 500
MIN_CADENCE_SECONDS = 0.05
SECTION_ARGUMENTS = 3

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from redis.asyncio import Redis

RUNTIME_KEYS = frozenset(
    {
        "game.cadence.walk_seconds",
        "game.cadence.attack_seconds",
        "game.cadence.cast_seconds",
        "game.cadence.work_seconds",
        "game.combat.pvp_enabled",
    }
)


async def load_runtime_settings(redis: Redis) -> None:
    """Restaura únicamente los parámetros de juego editables, nunca credenciales.

    Raises:
        ValueError: Si los datos o precondiciones de la operación son inválidos.
    """
    rows = await redis.hgetall("config:runtime")
    for name, value in rows.items():
        if name in RUNTIME_KEYS:
            parsed = json.loads(value)
            if name.endswith("pvp_enabled"):
                valid = type(parsed) is bool
            else:
                valid = (
                    type(parsed) in {float, int}
                    and MIN_CADENCE_SECONDS <= parsed <= MAX_CADENCE_SECONDS
                )
            if not valid:
                message = f"Parámetro de juego persistido inválido: {name}"
                raise ValueError(message)
            config_manager.set(name, parsed)


async def access(ctx: ChatContext) -> None:
    """Alterna el acceso de usuarios; el login consulta esta política persistida."""
    key = "server:admission"

    def decide(snapshot: Snapshot) -> Decision:
        current = cast("dict[str, str]", snapshot[key])
        restricted = current.get("gm_only") != "1"
        return Decision(
            {"applied": True, "restricted": restricted},
            {key: {"gm_only": "1" if restricted else "0"}},
        )

    result = await audited(ctx, (Resource(key, "hash"),), {"admission": True}, decide)
    await ctx.tell(
        "Servidor restringido a GM." if result["restricted"] else "Servidor habilitado para todos."
    )


async def motd(ctx: ChatContext) -> None:
    """Cambia el mensaje que reciben las nuevas conexiones al entrar.

    Raises:
        ChatCommandError: Si los datos o precondiciones de la operación son inválidos.
    """
    if not ctx.arguments or len(ctx.arguments) > MAX_MOTD_LENGTH:
        message = "Uso: /MOTDCAMBIA mensaje (hasta 500 caracteres)"
        raise ChatCommandError(message)
    key = "server:motd"
    await audited(
        ctx,
        (Resource(key, "string"),),
        {"motd": True},
        lambda _snapshot: Decision({"applied": True}, {key: ctx.arguments}),
    )
    await ctx.tell("Mensaje de bienvenida actualizado.")


async def settings(ctx: ChatContext) -> None:
    """Edita una lista acotada de parámetros, con tipo y límites explícitos.

    Raises:
        ChatCommandError: Si los datos o precondiciones de la operación son inválidos.
    """
    parts = ctx.arguments.split(maxsplit=2)
    if len(parts) == SECTION_ARGUMENTS:
        key, raw = f"{parts[0]}.{parts[1]}", parts[2]
    elif len(parts) == KEY_ARGUMENTS:
        key, raw = parts
    else:
        message = "Uso: /SETINIVAR game.cadence.walk_seconds valor (o sección clave valor)"
        raise ChatCommandError(message)
    key = key.lower()
    if key not in RUNTIME_KEYS:
        message = "Parámetros editables: " + ", ".join(sorted(RUNTIME_KEYS))
        raise ChatCommandError(message)
    value = json.loads(raw.lower())
    if key.endswith("pvp_enabled"):
        if type(value) is not bool:
            message = "Usa true o false."
            raise ChatCommandError(message)
    elif type(value) not in {int, float} or not MIN_CADENCE_SECONDS <= value <= MAX_CADENCE_SECONDS:
        message = "El intervalo debe estar entre 0.05 y 30 segundos."
        raise ChatCommandError(message)
    await fields(ctx, "config:runtime", {key: json.dumps(value)})
    config_manager.set(key, value)
    await ctx.tell(f"Configuración persistida: {key} = {value}.")


async def reload_data(ctx: ChatContext) -> None:
    """Recarga el objeto compartido para que las acciones siguientes usen los cambios."""
    await audited(
        ctx, (), {"reload": ctx.command}, lambda _snapshot: Decision({"applied": True}, {})
    )
    if ctx.command == "/RELOADNPCS":
        count = ctx.deps.npc_catalog.reload()
    elif ctx.command == "/RELOADHECHIZOS":
        count = ctx.deps.spell_catalog.reload()
    elif ctx.command == "/RELOADOBJ":
        count = ctx.deps.item_catalog.reload()
    else:
        config_manager.reload()
        await load_runtime_settings(ctx.redis)
        count = len(RUNTIME_KEYS)
    await ctx.tell(
        f"Recarga completada: {count} definiciones. "
        "Las conexiones y recursos ya creados conservan su ciclo de vida."
    )


async def save(ctx: ChatContext) -> None:
    """Confirma la barrera de AOF; no reescribe personajes desde snapshots viejos."""
    await require_durable(ctx.redis)
    await fields(ctx, "world:save", {"at": str(int(time.time())), "actor": str(ctx.user)})
    await ctx.tell("Partidas confirmadas en Redis/AOF.")


async def backup(ctx: ChatContext) -> None:
    """Solicita un RDB al Redis configurado y confirma que la generación terminó.

    Raises:
        ChatCommandError: Si los datos o precondiciones de la operación son inválidos.
    """
    await audited(
        ctx, (), {"backup": "redis-rdb"}, lambda _snapshot: Decision({"applied": True}, {})
    )
    started = int(time.time())
    await ctx.redis.bgsave()
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        info = await ctx.redis.info("persistence")
        if not info.get("rdb_bgsave_in_progress"):
            if (
                info.get("rdb_last_bgsave_status") != "ok"
                or int(info.get("rdb_last_save_time", 0)) < started
            ):
                message = "Redis no confirmó un snapshot RDB correcto."
                raise ChatCommandError(message)
            await fields(
                ctx, "world:backup", {"at": str(info["rdb_last_save_time"]), "actor": str(ctx.user)}
            )
            await ctx.tell(
                "Snapshot RDB completado en el almacenamiento de Redis. "
                "Para copiarlo y verificar restauración, "
                "usa la herramienta de backups del operador."
            )
            return
        await asyncio.sleep(0.05)
    message = "El snapshot sigue en curso; no se confirmó como finalizado."
    raise ChatCommandError(message)


async def stop(ctx: ChatContext) -> None:
    """Pide cierre o reinicio real, después de confirmar y drenar la respuesta.

    Raises:
        ChatCommandError: Si los datos o precondiciones de la operación son inválidos.
    """
    if ctx.deps.admin_control is None:
        message = "El control del proceso no está disponible en este entorno."
        raise ChatCommandError(message)
    restart = ctx.command == "/REINICIAR"
    await audited(ctx, (), {"restart": restart}, lambda _snapshot: Decision({"applied": True}, {}))
    await ctx.tell("Reiniciando el servidor..." if restart else "Apagando el servidor...")
    await ctx.sender.connection.flush()
    ctx.deps.admin_control(restart)


async def autoupdate(ctx: ChatContext) -> None:
    """Reinicia el agente del operador que reemplaza al aoau.exe de VB6.

    Raises:
        ChatCommandError: Si los datos o precondiciones de la operación son inválidos.
    """
    configured = str(config_manager.get("server.autoupdate_hook", ""))
    path = Path(configured) if configured else None
    if path is None or not path.is_absolute() or path.is_symlink() or not path.is_file():
        message = (
            "El operador debe configurar server.autoupdate_hook con el agente de actualización "
            "de su distribución. Snap conserva sus actualizaciones mediante snapd."
        )
        raise ChatCommandError(message)
    mode = path.stat()
    if (
        mode.st_mode & (stat.S_IWGRP | stat.S_IWOTH)
        or not os.access(path, os.X_OK)
        or (hasattr(os, "geteuid") and mode.st_uid != os.geteuid())
    ):
        message = "El agente debe ser ejecutable y no admitir escritura de grupo/otros."
        raise ChatCommandError(message)
    await audited(
        ctx,
        (),
        {"autoupdate": "configured-agent"},
        lambda _snapshot: Decision({"applied": True}, {}),
    )
    process = await asyncio.create_subprocess_exec(
        str(path),
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
        env={"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "LANG": "C.UTF-8"},
    )
    try:
        async with asyncio.timeout(30):
            result = await process.wait()
    except TimeoutError:
        process.kill()
        await process.wait()
        message = "El agente excedió el plazo; no se confirmó la actualización."
        raise ChatCommandError(message) from None
    if result:
        message = "El agente falló; revisa su registro local."
        raise ChatCommandError(message)
    await ctx.tell("Agente de actualización ejecutado correctamente.")


HANDLERS: dict[str, Callable[[ChatContext], Awaitable[None]]] = {
    "/HABILITAR": access,
    "/MOTDCAMBIA": motd,
    "/SETINIVAR": settings,
    "/GRABAR": save,
    "/DOBACKUP": backup,
    "/APAGAR": stop,
    "/REINICIAR": stop,
    "/AUTOUPDATE": autoupdate,
    **dict.fromkeys(("/RELOADNPCS", "/RELOADSINI", "/RELOADHECHIZOS", "/RELOADOBJ"), reload_data),
}
