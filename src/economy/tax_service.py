"""Cobro fiscal durable y resumen que no depende de una sesión conectada."""

from typing import TYPE_CHECKING

from src.economy.tax_transactions import money_revision_key, tax_key
from src.economy.taxes import SECONDS_PER_DAY, TAX_POLICY_KEY, utc_day
from src.utils.durability import require_durable
from src.utils.gold_atomic import operation_id
from src.utils.redis_config import RedisKeys
from src.utils.resource_transaction import Decision, Resource, transact

if TYPE_CHECKING:
    from redis.asyncio import Redis


async def settle_user_taxes(redis: Redis, user_id: int) -> None:
    """Materializa días pendientes antes de leer el saldo; un día se cobra una vez."""
    previous = await redis.hget(tax_key(user_id), "last_day")
    if previous is not None and int(previous) >= utc_day():
        return
    if not await redis.exists(TAX_POLICY_KEY):
        return
    if not await redis.exists(RedisKeys.player_user_stats(user_id)):
        return
    await require_durable(redis)
    await transact(
        redis,
        (Resource(RedisKeys.player_user_stats(user_id), "hash"),),
        operation_id(),
        {"tax_settlement": user_id},
        lambda _snapshot: Decision({"applied": True}, {}),
    )
    await require_durable(redis)


async def tax_status(redis: Redis, user_id: int) -> dict[str, object]:
    """Consulta el estado fiscal del personaje autenticado.

    Returns:
        Política, saldos liquidados y último recibo de cobro.
    """
    await settle_user_taxes(redis, user_id)
    async with redis.pipeline(transaction=True) as pipe:
        pipe.hgetall(TAX_POLICY_KEY)
        pipe.hgetall(tax_key(user_id))
        pipe.hget(RedisKeys.player_user_stats(user_id), "gold")
        pipe.get(RedisKeys.bank_gold(user_id))
        pipe.get(money_revision_key(user_id))
        policy, state, wallet_value, bank_value, revision = await pipe.execute()
    wallet, bank = int(wallet_value or 0), int(bank_value or 0)
    return {
        "money_revision": int(revision or 0),
        "rate_bps": int(policy.get("rate_bps", 0)),
        "enabled": policy.get("enabled") == "1",
        "scope": "wallet_and_bank",
        "wallet": wallet,
        "bank": bank,
        "last_day": int(state.get("last_day", utc_day())),
        "last_charge": int(state.get("last_charge", 0)),
        "from_day": int(state.get("last_from_day", utc_day())),
        "receipt": state.get("last_receipt", ""),
        "total_paid": int(state.get("total_paid", 0)),
        "next_cutoff": (utc_day() + 1) * SECONDS_PER_DAY,
    }
