"""Regla de bloqueo persistente, compartida por autenticación y reservas de sesión."""

import math
import time
from collections.abc import Mapping
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from redis.asyncio import Redis


def ban_key(user_id: int) -> str:
    """Identifica el estado de moderación de una cuenta.

    Returns:
        Clave independiente de la conexión activa.
    """
    return f"account:ban:{user_id}"


def is_blocked(fields: Mapping[str, str], *, prefix: str = "", now: float | None = None) -> bool:
    """Conserva el historial al vencer un bloqueo, sin exigir un worker de limpieza.

    Returns:
        Si la cuenta está bloqueada en el instante consultado.

    Raises:
        ValueError: Si el registro de bloqueo es incompatible o corrupto.
    """
    active = fields.get(f"{prefix}active", "0")
    if active == "0":
        return False
    expires = float(fields.get(f"{prefix}expires", "0"))
    if active != "1" or not math.isfinite(expires) or expires < 0:
        message = "Estado de bloqueo de cuenta inválido"
        raise ValueError(message)
    return expires == 0 or expires > (time.time() if now is None else now)


async def account_is_blocked(redis: Redis, user_id: int) -> bool:
    """Lee sólo el estado de la cuenta solicitada.

    Returns:
        Regla efectiva de bloqueo, sin exponer motivos o actores al cliente.
    """
    async with redis.pipeline(transaction=True) as pipe:
        pipe.hgetall(ban_key(user_id))
        result = await pipe.execute()
    return is_blocked(result[0])
