"""Reemplazo autenticado del hash con CAS, recibo y consulta de resultado sin secretos."""

from hmac import compare_digest
from typing import TYPE_CHECKING, Any, TypedDict, cast

from src.network.packet_builder import PacketBuilder
from src.security.password_executor import PasswordQueueFullError, get_password_executor
from src.utils.durability import require_durable
from src.utils.gold_atomic import operation_id
from src.utils.password_utils import hash_password, verify_password
from src.utils.redis_config import RedisKeys
from src.utils.resource_transaction import (
    Decision,
    Resource,
    Snapshot,
    read_resource_receipt,
    transact,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable

    from redis.asyncio import Redis

MIN_PASSWORD_BYTES = 6
MAX_PASSWORD_BYTES = 32
REPLY_PACKET_ID = 253


class PasswordResult(TypedDict):
    """Único resultado público; los hashes del recibo nunca salen de Redis/servicio."""

    applied: bool
    message: str


def password_valid(value: str) -> bool:
    """Aplica los mismos límites y codec literales que login/alta.

    Returns:
        Si contiene entre seis y 32 bytes Latin-1 sin sustitución de caracteres.
    """
    try:
        encoded = value.encode("latin-1")
    except UnicodeEncodeError:
        return False
    return MIN_PASSWORD_BYTES <= len(encoded) <= MAX_PASSWORD_BYTES


def _public(result: dict[str, Any]) -> PasswordResult:
    return {"applied": result.get("applied") is True, "message": str(result.get("message", ""))}


async def _matches(result: dict[str, Any], current: str, new: str) -> bool:
    previous, replacement = result.get("previous_hash"), result.get("next_hash")
    if not isinstance(previous, str) or not isinstance(replacement, str):
        return False
    pool = get_password_executor()
    return await pool.run(verify_password, current, previous) and await pool.run(
        verify_password, new, replacement
    )


async def change_password(
    redis: Redis, username: str, user_id: int, identity: str, current: str, new: str
) -> PasswordResult:
    """Verifica fuera del loop y sustituye sólo el hash que fue autenticado.

    Returns:
        Éxito durable o rechazo, sin devolver hashes ni contraseñas.
    """
    key = RedisKeys.account_data(username)
    resources = (Resource(key, "hash"),)
    request = {"password_change": user_id}
    cached = await read_resource_receipt(redis, resources, identity, request)
    valid = password_valid(current) and password_valid(new)
    if cached is not None:
        if not valid or (
            cached.get("applied") is True and not await _matches(cached, current, new)
        ):
            return {"applied": False, "message": "Identificador reutilizado o credencial inválida."}
        await require_durable(redis)
        return _public(cached)
    account = await cast("Awaitable[dict[str, str]]", redis.hgetall(key))
    expected = account.get("password_hash", "")
    replacement = ""
    rejection = ""
    if account.get("user_id") != str(user_id):
        rejection = "La cuenta no pertenece a esta sesión."
    elif not valid:
        rejection = "La contraseña debe tener entre 6 y 32 bytes Latin-1."
    else:
        try:
            pool = get_password_executor()
            if await pool.run(verify_password, current, expected):
                replacement = await pool.run(hash_password, new)
            else:
                rejection = "La contraseña actual es incorrecta."
        except PasswordQueueFullError:
            rejection = "Servicio de autenticación ocupado; reintentá más tarde."

    def decide(snapshot: Snapshot) -> Decision:
        saved = cast("dict[str, str]", snapshot[key])
        if rejection:
            return Decision({"applied": False, "message": rejection}, {})
        if saved.get("user_id") != str(user_id) or saved.get("password_hash") != expected:
            return Decision(
                {"applied": False, "message": "La cuenta cambió durante la operación."}, {}
            )
        result = {
            "applied": True,
            "message": "Contraseña actualizada.",
            "previous_hash": expected,
            "next_hash": replacement,
        }
        return Decision(result, {key: {"password_hash": replacement}})

    await require_durable(redis)
    result = await transact(redis, resources, identity, request, decide)
    await require_durable(redis)
    if result.get("applied") is not True:
        return _public(result)
    # Un segundo caller puede haber ganado con otra sal o incluso otro contenido.
    own_hashes = compare_digest(str(result.get("previous_hash", "")), expected) and compare_digest(
        str(result.get("next_hash", "")), replacement
    )
    if (
        result.get("applied") is True
        and not own_hashes
        and not await _matches(result, current, new)
    ):
        return {"applied": False, "message": "Identificador reutilizado para otra contraseña."}
    return _public(result)


async def password_change_status(
    redis: Redis, username: str, user_id: int, identity: str
) -> tuple[int, str]:
    """Permite recuperar un ack perdido sin conservar ni volver a pedir las claves.

    Returns:
        Estado 1 aplicado, 2 rechazado o 3 indeterminado; no interpreta ausencia como fracaso.
    """
    result = await read_resource_receipt(
        redis,
        (Resource(RedisKeys.account_data(username), "hash"),),
        identity,
        {"password_change": user_id},
    )
    if result is None:
        return 3, "No hay resultado confirmado; verificá la contraseña al volver a ingresar."
    await require_durable(redis)
    return (1 if result.get("applied") is True else 2), str(result.get("message", ""))


def build_password_reply(
    identity: str = "", status: int = 0, message: str = "", *, next_identity: str | None = None
) -> bytes:
    """Serializa sólo metadatos públicos y el próximo ID generado por el servidor.

    Returns:
        Paquete optativo 253, nunca hashes ni credenciales.
    """
    return (
        PacketBuilder()
        .add_byte(REPLY_PACKET_ID)
        .add_byte(1)
        .add_unicode_string(identity)
        .add_unicode_string(next_identity or operation_id())
        .add_byte(status)
        .add_unicode_string(message[:160])
        .to_bytes()
    )
