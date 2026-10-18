"""Cambio y consulta de contraseña autenticados, sin logs ni eco de credenciales."""

from time import monotonic
from typing import TYPE_CHECKING, Any

from redis.exceptions import RedisError

from src.network.capabilities import Capability
from src.network.session_manager import SessionManager
from src.services.password_change import (
    build_password_reply,
    change_password,
    password_change_status,
)
from src.tasks.task import Task
from src.utils.gold_atomic import validate_operation_id

if TYPE_CHECKING:
    from src.messaging.message_sender import MessageSender
    from src.repositories.account_repository import AccountRepository

MAX_ID_BYTES = 46
MAX_PASSWORD_BYTES = 32
STATUS_INTERVAL_SECONDS = 1.0
PACKET_PREFIX_BYTES = 2


def _parse(data: bytes) -> tuple[str, str, str] | None:
    if len(data) < PACKET_PREFIX_BYTES or data[1] != 1:
        return None
    offset = 2
    values: list[str] = []
    for limit in (MAX_ID_BYTES, MAX_PASSWORD_BYTES, MAX_PASSWORD_BYTES):
        if len(data) < offset + 2:
            return None
        size = int.from_bytes(data[offset : offset + 2], "little")
        offset += 2
        if size > limit or len(data) < offset + size:
            return None
        values.append(data[offset : offset + size].decode("latin-1"))
        offset += size
    if offset != len(data):
        return None
    if values[0]:
        try:
            validate_operation_id(values[0])
        except ValueError:
            return None
    return values[0], values[1], values[2]


class TaskChangePassword(Task):
    """El cliente no elige otra cuenta ni recibe hashes en las respuestas."""

    def __init__(
        self,
        data: bytes,
        message_sender: MessageSender,
        account_repo: AccountRepository,
        session_data: dict[str, Any] | None = None,
    ) -> None:
        """Recibe exclusivamente la sesión de la conexión actual."""
        super().__init__(data, message_sender)
        self.account_repo = account_repo
        self.session_data = session_data if session_data is not None else {}

    async def execute(self) -> None:
        """Negocia un ID, confirma un cambio o consulta el resultado del ID original."""
        connection = self.message_sender.connection
        user_id = SessionManager.get_user_id(self.session_data)
        username = self.session_data.get("username")
        if (
            not connection.is_authenticated
            or not user_id
            or not isinstance(username, str)
            or not connection.capabilities.enabled & Capability.PASSWORD_CHANGE
        ):
            return
        parsed = _parse(self.data)
        self.data = b""  # No conservar otra copia del paquete que contiene las claves.
        if parsed is None:
            return
        identity, current, new = parsed
        status, message = 0, ""
        try:
            if not current and not new:
                now = monotonic()
                if now < connection.password_status_after:
                    return
                connection.password_status_after = now + STATUS_INTERVAL_SECONDS
                if identity:
                    status, message = await password_change_status(
                        self.account_repo.redis.redis, username, user_id, identity
                    )
            elif not identity:
                status, message = 2, "Primero solicitá un identificador de operación."
            elif not connection.allow_password_change(username):
                status, message = 2, "Demasiados intentos; esperá antes de reintentar."
            else:
                result = await change_password(
                    self.account_repo.redis.redis, username, user_id, identity, current, new
                )
                status = 1 if result["applied"] else 2
                message = result["message"]
        except ValueError:
            status, message = 2, "Solicitud inválida, vencida o reutilizada."
        except RedisError, RuntimeError:
            status, message = 3, "No se pudo confirmar el resultado; verificá al volver a ingresar."
        await connection.send(build_password_reply(identity, status, message))
