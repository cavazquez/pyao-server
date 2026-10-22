"""Operaciones administrativas de cuentas e historial sin divulgar credenciales."""

import json
import re
import time
from typing import TYPE_CHECKING, cast

from src.network.client_connection import ClientConnection
from src.repositories.account_repository import USER_ACCOUNT_INDEX
from src.services.classic_chat.context import ChatCommandError, ChatContext
from src.utils.gold_atomic import operation_id
from src.utils.redis_config import RedisKeys
from src.utils.resource_transaction import Decision, Resource, Snapshot

MAX_EMAIL_LENGTH = 254
MAX_WARNING_LENGTH = 200
PAIR_ARGUMENTS = 2

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable


def pair(arguments: str) -> tuple[str, str]:
    """Acepta el separador clásico @ o dos argumentos modernos.

    Returns:
        Objetivo y segundo valor, conservando su contenido.

    Raises:
        ChatCommandError: Si los datos o precondiciones de la operación son inválidos.
    """
    parts = arguments.split("@", 1) if "@" in arguments else arguments.split(maxsplit=1)
    if len(parts) != PAIR_ARGUMENTS or not all(part.strip() for part in parts):
        message = "Faltan argumentos."
        raise ChatCommandError(message)
    return parts[0].strip(), parts[1].strip()


async def password_copy(ctx: ChatContext) -> None:
    """Conserva /APASS destino@origen: copia el hash, nunca una clave en claro."""
    target_name, source_name = pair(ctx.arguments)
    target, source = await ctx.account(target_name), await ctx.account(source_name)
    user = int(target["user_id"])
    target_key, source_key = (
        RedisKeys.account_data(target["username"]),
        RedisKeys.account_data(source["username"]),
    )
    lease = f"session:{user}:owner"
    audit = f"moderation:change:{operation_id()}"

    def decide(snapshot: Snapshot) -> Decision:
        before = cast("dict[str, str]", snapshot[target_key])
        donor = cast("dict[str, str]", snapshot[source_key])
        hashed = donor.get("password_hash", "")
        if before.get("user_id") != str(user) or not hashed.startswith("$argon2id$"):
            return Decision(
                {"applied": False, "message": "Las cuentas ya no tienen un estado válido."}, {}
            )
        return Decision(
            {"applied": True, "message": "Contraseña transferida; sesiones anteriores revocadas."},
            {
                target_key: {"password_hash": hashed},
                lease: "",
                audit: json.dumps(
                    {
                        "actor": ctx.user,
                        "target": user,
                        "source": source["user_id"],
                        "action": "password_copy",
                        "at": int(time.time()),
                    }
                ),
            },
        )

    resources = tuple(
        {
            resource.key: resource
            for resource in (
                Resource(target_key, "hash"),
                Resource(source_key, "hash"),
                Resource(lease, "string"),
                Resource(audit, "string"),
            )
        }.values()
    )
    result = await ctx.commit(resources, {"target": user, "source": source["user_id"]}, decide)
    if result["applied"]:
        ClientConnection.revoke_user(user, ctx.redis)
    await ctx.tell(result["message"])


async def email(ctx: ChatContext) -> None:
    """Actualiza sólo el correo de una cuenta existente.

    Raises:
        ChatCommandError: Si los datos o precondiciones de la operación son inválidos.
    """
    # El separador histórico es guion; @ y espacio se aceptan si separan
    # explícitamente el nombre del correo completo.
    if " " not in ctx.arguments and "-" in ctx.arguments and ctx.arguments.count("@") == 1:
        name, address = ctx.arguments.split("-", 1)
    else:
        name, address = pair(ctx.arguments)
    if (
        not re.fullmatch(r"[^\s@]{1,64}@[^\s@]{1,189}\.[^\s@]{2,63}", address)
        or len(address) > MAX_EMAIL_LENGTH
    ):
        message = "Correo inválido."
        raise ChatCommandError(message)
    target = await ctx.account(name)
    key = RedisKeys.account_data(target["username"])
    result = await ctx.commit(
        (Resource(key, "hash"),),
        {"target": target["user_id"], "field": "email"},
        lambda _snapshot: Decision(
            {"applied": True, "message": "Correo actualizado."}, {key: {"email": address}}
        ),
    )
    await ctx.tell(result["message"])


async def rename(ctx: ChatContext) -> None:
    """Renombra una cuenta desconectada y sin clan/grupo conservando su user_id.

    Raises:
        ChatCommandError: Si los datos o precondiciones de la operación son inválidos.
    """
    old, new = pair(ctx.arguments)
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{2,19}", new):
        message = "El nombre debe tener entre 3 y 20 letras, números o guion bajo."
        raise ChatCommandError(message)
    account = await ctx.account(old)
    user = int(account["user_id"])
    if ctx.deps.map_manager.get_player_message_sender(user) is not None:
        message = "El personaje debe estar desconectado para cambiar de nombre."
        raise ChatCommandError(message)
    if await ctx.deps.party_service.get_party_info(user) or await ctx.deps.clan_repo.get_user_clan(
        user
    ):
        message = "El personaje debe salir de su party y clan antes de cambiar de nombre."
        raise ChatCommandError(message)
    old_key, new_key = RedisKeys.account_data(account["username"]), RedisKeys.account_data(new)
    old_index, new_index = (
        RedisKeys.account_id_by_username(account["username"]),
        RedisKeys.account_id_by_username(new),
    )
    lease, clan_key = f"session:{user}:owner", f"user:{user}:clan"

    def decide(snapshot: Snapshot) -> Decision:
        previous = cast("dict[str, str]", snapshot[old_key])
        index = cast("dict[str, str]", snapshot[USER_ACCOUNT_INDEX])
        if snapshot[new_key] or snapshot[new_index] or snapshot[lease] or snapshot[clan_key]:
            return Decision(
                {
                    "applied": False,
                    "message": (
                        "El nombre ya existe o el personaje volvió a "
                        "conectarse/ingresar en un clan."
                    ),
                },
                {},
            )
        if previous.get("user_id") != str(user) or index.get(str(user)) != account["username"]:
            return Decision({"applied": False, "message": "La identidad cambió."}, {})
        return Decision(
            {
                "applied": True,
                "message": f"Nombre actualizado a {new}; el personaje conserva su partida.",
            },
            {
                new_key: {**previous, "username": new},
                new_index: str(user),
                USER_ACCOUNT_INDEX: {str(user): new},
                old_key: None,
                old_index: "0",
            },
        )

    resources = (
        Resource(old_key, "hash", deletable=True),
        Resource(new_key, "hash"),
        Resource(old_index, "string"),
        Resource(new_index, "string"),
        Resource(USER_ACCOUNT_INDEX, "hash"),
        Resource(lease, "string"),
        Resource(clan_key, "string"),
    )
    result = await ctx.commit(resources, {"target": user, "new_name": new}, decide)
    await ctx.tell(result["message"])


async def warning(ctx: ChatContext) -> None:
    """Agrega una advertencia a las penas públicas y notifica al destinatario.

    Raises:
        ChatCommandError: Si los datos o precondiciones de la operación son inválidos.
    """
    name, reason = pair(ctx.arguments)
    if len(reason) > MAX_WARNING_LENGTH:
        message = "El motivo no puede superar 200 caracteres."
        raise ChatCommandError(message)
    target = await ctx.account(name)
    user = int(target["user_id"])
    key = f"moderation:penalties:{user}"
    identity = operation_id()
    record = json.dumps(
        {"kind": "advertencia", "reason": reason, "actor": ctx.user, "at": int(time.time())}
    )
    result = await ctx.commit(
        (Resource(key, "hash"),),
        {"target": user},
        lambda _snapshot: Decision(
            {"applied": True, "message": "Advertencia registrada."}, {key: {identity: record}}
        ),
    )
    sender = ctx.deps.map_manager.get_player_message_sender(user)
    if sender and result["applied"]:
        await sender.send_console_msg(f"Advertencia de administración: {reason}")
    await ctx.tell(result["message"])


async def remove_penalty(ctx: ChatContext) -> None:
    """Retira una pena por identidad, conservando una marca de auditoría."""
    name, identity = pair(ctx.arguments)
    target = await ctx.account(name)
    key = f"moderation:penalties:{target['user_id']}"
    audit = f"moderation:removed:{operation_id()}"

    def decide(snapshot: Snapshot) -> Decision:
        values = cast("dict[str, str]", snapshot[key])
        if identity not in values:
            return Decision(
                {"applied": False, "message": "Pena no encontrada; usa su identificador."}, {}
            )
        record = json.loads(values[identity])
        return Decision(
            {"applied": True, "message": "Pena retirada del prontuario público."},
            {
                key: {identity: json.dumps({**record, "removed": True})},
                audit: json.dumps(
                    {
                        "actor": ctx.user,
                        "target": target["user_id"],
                        "penalty": identity,
                        "at": int(time.time()),
                    }
                ),
            },
        )

    result = await ctx.commit(
        (Resource(key, "hash"), Resource(audit, "string")),
        {"target": target["user_id"], "penalty": identity},
        decide,
    )
    await ctx.tell(result["message"])


async def silence_denounces(ctx: ChatContext) -> None:
    """Alterna sólo denuncias, como /SILENCIAR clásico; no bloquea /GM."""
    target = await ctx.account(ctx.arguments)
    key = RedisKeys.player_user_stats(int(target["user_id"]))

    def decide(snapshot: Snapshot) -> Decision:
        current = cast("dict[str, str]", snapshot[key])
        active = current.get("denounces_muted") != "1"
        return Decision(
            {
                "applied": True,
                "message": "Denuncias silenciadas." if active else "Denuncias habilitadas.",
            },
            {key: {"denounces_muted": "1" if active else "0"}},
        )

    result = await ctx.commit((Resource(key, "hash"),), {"target": target["user_id"]}, decide)
    await ctx.tell(result["message"])


HANDLERS: dict[str, Callable[[ChatContext], Awaitable[None]]] = {
    "/APASS": password_copy,
    "/AEMAIL": email,
    "/ANAME": rename,
    "/ADVERTENCIA": warning,
    "/BORRARPENA": remove_penalty,
    "/SILENCIAR": silence_denounces,
}
