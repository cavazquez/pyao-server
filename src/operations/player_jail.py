"""Administrar el plazo de condena registrado y mostrado en estadísticas (días reales)."""

import argparse
import asyncio
import json
import time
from typing import TYPE_CHECKING, cast

from src.config.config_manager import config_manager
from src.config.game_config import RedisConfig
from src.repositories.account_repository import AccountRepository
from src.services.player.lifetime_stats import DAY_SECONDS
from src.utils.durability import require_durable
from src.utils.gold_atomic import operation_id
from src.utils.redis_client import RedisClient
from src.utils.redis_config import RedisKeys
from src.utils.resource_transaction import Decision, Resource, Snapshot, transact

if TYPE_CHECKING:
    from typing import Any

    from redis.asyncio import Redis

MAX_SENTENCE_DAYS = 365
MAX_REASON_LENGTH = 256


async def sentence(
    redis: Redis, user: int, days: int, reason: str, identity: str, *, now: float | None = None
) -> dict[str, Any]:
    """Registra una condena administrativa o la libera con cero; un replay no la prolonga.

    Returns:
        Plazo absoluto confirmado, persistido junto al motivo.

    Raises:
        ValueError: Por objetivo, duración o motivo inválidos.
    """
    if (
        user < 1
        or not 0 <= days <= MAX_SENTENCE_DAYS
        or not reason.strip()
        or len(reason) > MAX_REASON_LENGTH
    ):
        message = "Condena inválida: usuario existente, 0..365 días y motivo de 1..256 caracteres"
        raise ValueError(message)
    now = time.time() if now is None else now
    key = RedisKeys.player_user_stats(user)

    def decide(snapshot: Snapshot) -> Decision:
        if not snapshot[key]:
            message = "El personaje no existe; no se crea una condena huérfana"
            raise ValueError(message)
        fields = {
            "jail_until": str(int(now + days * DAY_SECONDS) if days else 0),
            "jail_total_days": str(days),
            "jail_reason": reason.strip(),
        }
        return Decision(cast("dict[str, Any]", dict(fields)), {key: fields})

    result = await transact(
        redis,
        (Resource(key, "hash"),),
        identity,
        {"sentence": user, "days": days, "reason": reason.strip()},
        decide,
    )
    await require_durable(redis)
    return result


async def administer(username: str, days: int, reason: str) -> dict[str, Any]:
    """La CLI requiere acceso administrativo al endpoint y al secreto de Redis.

    Returns:
        Resultado de la condena del personaje resuelto por su cuenta real.

    Raises:
        ValueError: Si no existe la cuenta.
    """
    client = RedisClient()
    await client.connect(
        RedisConfig.model_validate(config_manager.get_section("redis")), seed_defaults=False
    )
    try:
        profile = await AccountRepository(client).get_account(username)
        user = int(profile["user_id"]) if profile else None
        if user is None:
            message = "La cuenta no existe"
            raise ValueError(message)
        return await sentence(client.redis, user, days, reason, operation_id())
    finally:
        await client.disconnect()


def main() -> None:
    """No expone al cliente de juego la posibilidad de editar condenas."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("username")
    parser.add_argument("--days", type=int, required=True)
    parser.add_argument("--reason", required=True)
    args = parser.parse_args()
    print(json.dumps(asyncio.run(administer(args.username, args.days, args.reason))))


if __name__ == "__main__":
    main()
