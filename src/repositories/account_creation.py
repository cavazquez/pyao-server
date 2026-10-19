"""Alta atómica de cuenta, índice y estado fiscal, sin reutilizar identidades."""

from typing import TYPE_CHECKING, cast

from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError
from redis.exceptions import WatchError

from src.economy.taxes import utc_day
from src.utils.gold_atomic import MAX_TRANSACTION_ATTEMPTS
from src.utils.redis_config import RedisKeys

if TYPE_CHECKING:
    from collections.abc import Mapping

    from redis.asyncio import Redis
    from redis.typing import EncodableT

ACCOUNT_INDEX = "account:index:user_id"


async def create_indexed_account(redis: Redis, username: str, fields: dict[str, str]) -> int:
    """Confirma contador, ambos índices, perfil y marcador fiscal en un EXEC.

    Returns:
        Identidad nueva cuya propiedad fue confirmada.

    Raises:
        ValueError: Si existe la cuenta o el contador intenta reutilizar una identidad.
        RuntimeError: Si no puede confirmar el alta tras reintentos acotados.
    """
    username_key, profile_key = (
        RedisKeys.account_id_by_username(username),
        RedisKeys.account_data(username),
    )
    for _attempt in range(MAX_TRANSACTION_ATTEMPTS):
        user_id = 0
        async with redis.pipeline() as pipe:
            try:
                await pipe.watch(
                    username_key, profile_key, RedisKeys.ACCOUNTS_COUNTER, ACCOUNT_INDEX
                )
                if await pipe.exists(username_key, profile_key):
                    message = f"La cuenta '{username}' ya existe"
                    raise ValueError(message)
                user_id = int(await pipe.get(RedisKeys.ACCOUNTS_COUNTER) or 0) + 1
                fiscal_key = f"tax:{user_id}:state"
                stats_key = RedisKeys.player_user_stats(user_id)
                await pipe.watch(fiscal_key, stats_key)
                if (
                    user_id < 1
                    or await pipe.hget(ACCOUNT_INDEX, str(user_id)) is not None
                    or await pipe.exists(fiscal_key, stats_key)
                ):
                    message = "El contador de cuentas intenta reutilizar una identidad existente"
                    raise ValueError(message)
                account = {**fields, "username": username, "user_id": str(user_id), "is_gm": "0"}
                fiscal = {
                    "version": "1",
                    "last_day": str(utc_day()),
                    "remainder": "0",
                    "total_paid": "0",
                }
                pipe.multi()  # type: ignore[no-untyped-call]
                pipe.set(RedisKeys.ACCOUNTS_COUNTER, str(user_id))
                pipe.set(username_key, str(user_id))
                pipe.hset(profile_key, mapping=cast("Mapping[EncodableT, EncodableT]", account))
                pipe.hset(ACCOUNT_INDEX, str(user_id), username)
                pipe.hset(fiscal_key, mapping=cast("Mapping[EncodableT, EncodableT]", fiscal))
                await pipe.execute()
            except WatchError:
                continue
            except RedisConnectionError, RedisTimeoutError:
                # Un ACK perdido no da lugar a un alta distinta ni pisa contraseñas.
                saved = await redis.hgetall(profile_key)
                if (
                    user_id
                    and saved
                    == {**fields, "username": username, "user_id": str(user_id), "is_gm": "0"}
                    and await redis.hget(ACCOUNT_INDEX, str(user_id)) == username
                    and await redis.get(username_key) == str(user_id)
                ):
                    return user_id
            else:
                return user_id
    message = "Alta no confirmada; consultá la cuenta antes de volver a crearla"
    raise RuntimeError(message)
