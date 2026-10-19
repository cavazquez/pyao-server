"""Moderación autorizada, auditable y atómica con la revocación de sesión."""

import json
import time
from typing import TYPE_CHECKING, Any, cast

from src.network.client_connection import ClientConnection
from src.repositories.account_repository import USER_ACCOUNT_INDEX
from src.security.account_bans import ban_key, is_blocked
from src.security.chat_mutes import moderate_chat
from src.utils.durability import require_durable
from src.utils.gold_atomic import operation_id
from src.utils.redis_config import RedisKeys
from src.utils.resource_transaction import Decision, Resource, Snapshot, transact

if TYPE_CHECKING:
    from src.repositories.account_repository import AccountRepository

MAX_BAN_DAYS = 3650
MAX_REASON_LENGTH = 120
SECONDS_PER_DAY = 86400


class AccountModeration:
    """Los permisos se verifican bajo WATCH y nunca provienen del texto del cliente."""

    def __init__(self, accounts: AccountRepository) -> None:
        """Conserva el repositorio e índice de identidades autorizados."""
        self.accounts = accounts

    async def apply(
        self,
        actor: int,
        username: str,
        *,
        active: bool,
        days: int,
        reason: str,
        identity: str | None = None,
    ) -> dict[str, Any]:
        """Registra un bloqueo/revocación y su auditoría en el mismo EXEC.

        Returns:
            Resultado identificado; un actor común no consulta datos del objetivo.
        """
        operator = await self.accounts.get_account_by_user_id(actor)
        if not operator or operator.get("is_gm") != "1" or is_blocked(operator, prefix="ban_"):
            return {"applied": False, "message": "No tienes permisos de moderación."}
        if (
            type(days) is not int
            or not 0 <= days <= MAX_BAN_DAYS
            or not reason.strip()
            or len(reason) > MAX_REASON_LENGTH
        ):
            return {"applied": False, "message": "Motivo o duración inválidos."}
        target = await self.accounts.get_account(username)
        if target is None:
            return {"applied": False, "message": "Cuenta objetivo no encontrada."}
        target_id = int(target["user_id"])
        if active and target_id == actor:
            return {"applied": False, "message": "No podés bloquear tu propia cuenta."}
        identity = identity or operation_id()
        now = int(time.time())
        expires = now + days * SECONDS_PER_DAY if active and days else 0
        profile = RedisKeys.account_data(username)
        operator_key = RedisKeys.account_data(operator["username"])
        key, lease, audit = (
            ban_key(target_id),
            f"session:{target_id}:owner",
            f"moderation:audit:{identity}",
        )
        fields = {
            "active": "1" if active else "0",
            "expires": str(expires),
            "reason": reason.strip(),
            "actor": str(actor),
            "target": str(target_id),
            "changed_at": str(now),
        }

        def decide(snapshot: Snapshot) -> Decision:
            index = cast("dict[str, str]", snapshot[USER_ACCOUNT_INDEX])
            admin = cast("dict[str, str]", snapshot[operator_key])
            current = cast("dict[str, str]", snapshot[profile])
            admin_identity = {name: admin.get(name) for name in ("user_id", "username", "is_gm")}
            expected_admin = {"user_id": str(actor), "username": operator["username"], "is_gm": "1"}
            target_identity = {name: current.get(name) for name in ("user_id", "username")}
            expected_target = {"user_id": str(target_id), "username": username}
            index_valid = all(
                index.get(str(identity)) == name
                for identity, name in ((actor, operator["username"]), (target_id, username))
            )
            if (
                admin_identity != expected_admin
                or target_identity != expected_target
                or not index_valid
                or is_blocked(admin, prefix="ban_")
            ):
                return Decision(
                    {"applied": False, "message": "La identidad o los permisos cambiaron."}, {}
                )
            if snapshot[audit] is not None:
                return Decision(
                    {"applied": False, "message": "Esta identidad de operación ya fue auditada."},
                    {},
                )
            writes: dict[str, str | dict[str, str]] = {
                key: fields,
                profile: {f"ban_{field}": value for field, value in fields.items()},
                audit: json.dumps(
                    {"action": "ban" if active else "unban", **fields}, ensure_ascii=True
                ),
            }
            if active:
                writes[lease] = ""  # Invalida el token sin reutilizarlo para otra conexión.
            return Decision(
                {
                    "applied": True,
                    "message": "Cuenta bloqueada." if active else "Bloqueo revocado.",
                    "target": target_id,
                    "expires": expires,
                },
                writes,
            )

        resources = tuple(
            {
                resource.key: resource
                for resource in (
                    Resource(USER_ACCOUNT_INDEX, "hash"),
                    Resource(operator_key, "hash"),
                    Resource(profile, "hash"),
                    Resource(key, "hash"),
                    Resource(lease, "string", ttl_seconds=1),
                    Resource(audit, "string"),
                )
            }.values()
        )
        redis = self.accounts.redis.redis
        await require_durable(redis)
        result = await transact(
            redis,
            resources,
            identity,
            {
                "moderation": target_id,
                "actor": actor,
                "active": active,
                "days": days,
                "reason": reason.strip(),
            },
            decide,
        )
        await require_durable(redis)
        if result["applied"] and active:
            ClientConnection.revoke_user(target_id, redis)
        return result

    async def handle_text(self, actor: int, text: str) -> dict[str, Any]:
        """Adapta /BAN nombre días motivo y /UNBAN nombre motivo sin ejecutar shell.

        Returns:
            Resultado o sintaxis corregible por el operador.
        """
        command = text.split(maxsplit=1)[0].upper()
        if command in {"/MUTE", "/UNMUTE"}:
            return await moderate_chat(self.accounts, actor, text)
        parts = text.split(maxsplit=3 if command == "/BAN" else 2)
        try:
            if command == "/BAN" and len(parts) == len(("command", "user", "days", "reason")):
                return await self.apply(
                    actor, parts[1], active=True, days=int(parts[2]), reason=parts[3]
                )
            if command == "/UNBAN" and len(parts) == len(("command", "user", "reason")):
                return await self.apply(actor, parts[1], active=False, days=0, reason=parts[2])
        except ValueError:
            pass
        return {
            "applied": False,
            "message": "Uso: /BAN nombre días motivo (0: permanente); /UNBAN nombre motivo.",
        }
