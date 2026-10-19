"""Silencios de chat con reloj del servidor, permisos observados y auditoría."""

import json
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

from src.security.account_bans import is_blocked
from src.utils.durability import require_durable
from src.utils.gold_atomic import operation_id
from src.utils.redis_config import RedisKeys
from src.utils.resource_transaction import Decision, Resource, Snapshot, transact

if TYPE_CHECKING:
    from redis.asyncio import Redis

    from src.repositories.account_repository import AccountRepository

CHANNELS = frozenset({"public", "whisper", "party", "clan"})
MAX_MUTE_MINUTES = 10080
MAX_REASON = 120
MUTE_PARTS = 5
UNMUTE_PARTS = 3


@dataclass(frozen=True)
class MuteRequest:
    """Intención validada; nunca contiene permisos proporcionados por el cliente."""

    username: str
    active: bool
    minutes: int
    channels: frozenset[str]
    reason: str


def parse_mute(text: str) -> MuteRequest:
    """Valida sintaxis, límites y canales antes de consultar el objetivo.

    Returns:
        Intención finita de moderación.

    Raises:
        ValueError: Por texto, duración o canal inválidos.
    """
    parts = text.split(maxsplit=4)
    active = bool(parts and parts[0].upper() == "/MUTE")
    if active:
        if len(parts) != MUTE_PARTS:
            raise ValueError
        minutes = int(parts[2])
        channels = CHANNELS if parts[3].lower() == "all" else frozenset(parts[3].lower().split(","))
        reason = parts[4].strip()
        if not 1 <= minutes <= MAX_MUTE_MINUTES or not channels or channels - CHANNELS:
            raise ValueError
    else:
        parts = text.split(maxsplit=2)
        if len(parts) != UNMUTE_PARTS or parts[0].upper() != "/UNMUTE":
            raise ValueError
        minutes, channels, reason = 0, frozenset(), parts[2].strip()
    if not reason or len(reason) > MAX_REASON:
        raise ValueError
    return MuteRequest(parts[1], active, minutes, channels, reason)


async def chat_rejection(redis: Redis, user: int, channel: str) -> str:
    """Consulta el silencio en cada envío, también después de una reconexión.

    Returns:
        Motivo visible al emisor o vacío si el canal está habilitado.
    """
    state = cast("dict[str, str]", await redis.hgetall(f"moderation:mute:{user}"))
    until = int(state.get("until", 0))
    if channel in state.get("channels", "").split(",") and until > time.time():
        minutes = max(1, (until - int(time.time()) + 59) // 60)
        return f"Chat silenciado por {minutes} min: {state.get('reason', '')}"
    return ""


async def moderate_chat(accounts: AccountRepository, actor: int, text: str) -> dict[str, Any]:
    """Interpreta /MUTE nombre minutos canales motivo y /UNMUTE nombre motivo.

    Returns:
        Resultado durable sin desconectar ni afectar acciones del juego.
    """
    operator = await accounts.get_account_by_user_id(actor)
    if not operator or operator.get("is_gm") != "1" or is_blocked(operator, prefix="ban_"):
        return {"applied": False, "message": "No tienes permisos de moderación."}
    try:
        request = parse_mute(text)
    except ValueError:
        return {
            "applied": False,
            "message": (
                "Uso: /MUTE nombre minutos public,whisper,party,clan|all motivo "
                "(máximo 10080 min); /UNMUTE nombre motivo."
            ),
        }
    target = await accounts.get_account(request.username)
    if not target:
        return {"applied": False, "message": "Cuenta objetivo no encontrada."}
    user = int(target["user_id"])
    identity, now = operation_id(), int(time.time())
    admin_key, target_key = (
        RedisKeys.account_data(operator["username"]),
        RedisKeys.account_data(request.username),
    )
    mute, audit = f"moderation:mute:{user}", f"moderation:audit:{identity}"
    fields = {
        "until": str(now + request.minutes * 60 if request.active else 0),
        "channels": ",".join(sorted(request.channels)),
        "reason": request.reason,
        "actor": str(actor),
        "target": str(user),
        "changed_at": str(now),
    }

    def decide(snapshot: Snapshot) -> Decision:
        admin, recipient = (
            cast("dict[str, str]", snapshot[key]) for key in (admin_key, target_key)
        )
        if (
            admin.get("is_gm") != "1"
            or int(admin.get("user_id", 0)) != actor
            or is_blocked(admin, prefix="ban_")
            or int(recipient.get("user_id", 0)) != user
        ):
            return Decision(
                {"applied": False, "message": "La identidad o los permisos cambiaron."}, {}
            )
        return Decision(
            {
                "applied": True,
                "message": "Silencio aplicado." if request.active else "Silencio revocado.",
            },
            {
                mute: fields,
                audit: json.dumps({"action": "mute" if request.active else "unmute", **fields}),
            },
        )

    redis = accounts.redis.redis
    await require_durable(redis)
    result = await transact(
        redis,
        tuple(
            {
                r.key: r
                for r in (
                    Resource(admin_key, "hash"),
                    Resource(target_key, "hash"),
                    Resource(mute, "hash", ttl_seconds=max(1, request.minutes * 60)),
                    Resource(audit, "string", ttl_seconds=604800),
                )
            }.values()
        ),
        identity,
        {"chat_moderation": fields},
        decide,
    )
    await require_durable(redis)
    return result
