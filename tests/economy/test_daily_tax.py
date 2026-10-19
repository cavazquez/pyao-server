"""Equivalencia online/offline, fracciones y concurrencia del impuesto diario."""

import asyncio
from unittest.mock import patch

import pytest

from src.economy.tax_service import tax_status
from src.economy.tax_transactions import money_revision_key, tax_key
from src.economy.taxes import MAX_BANK_GOLD, TAX_POLICY_KEY, assess_tax
from src.models.item_constants import MAX_PLAYER_GOLD
from src.services.bank_gold_transfer import transfer_gold
from src.utils.gold_atomic import change_gold, operation_id
from src.utils.redis_config import RedisKeys
from src.utils.resource_transaction import Decision, Resource, transact

DAY = 20_000


@pytest.mark.parametrize(
    ("wallet", "bank"),
    [(0, 0), (1, 0), (99, 1), (10_000, 20_000), (MAX_PLAYER_GOLD, MAX_BANK_GOLD)],
)
@pytest.mark.parametrize("days", [1, 2, 7, 31])
def test_offline_equals_daily_settlements(wallet, bank, days):
    """El mismo capital paga lo mismo conectado o ausente entre cortes."""
    offline = assess_tax(wallet, bank, DAY, DAY + days)
    remainder = 0
    for day in range(DAY + 1, DAY + days + 1):
        daily = assess_tax(wallet, bank, day - 1, day, remainder=remainder)
        wallet, bank, remainder = daily.wallet, daily.bank, daily.remainder
    assert (offline.wallet, offline.bank, offline.remainder) == (wallet, bank, remainder)


def test_small_balance_has_no_one_coin_daily_minimum():
    """Una moneda no paga el 100% en un día: sus fracciones se acumulan."""
    first = assess_tax(1, 0, DAY, DAY + 1)
    assert (first.wallet, first.charged, first.remainder) == (1, 0, 100)
    second = assess_tax(first.wallet, first.bank, DAY + 1, DAY + 2, remainder=first.remainder)
    assert (second.wallet, second.charged, second.remainder) == (1, 0, 200)
    assert assess_tax(1, 0, DAY, DAY + 100).wallet == 0


@pytest.mark.parametrize(("wallet", "bank"), [(100, 0), (99, 1), (1, 99), (0, 100)])
def test_dividing_gold_between_bank_and_wallet_does_not_avoid_tax(wallet, bank):
    """El impuesto usa el saldo total aunque cambie su distribución."""
    result = assess_tax(wallet, bank, DAY, DAY + 1)
    assert result.charged == 1
    assert result.wallet + result.bank == 99


def test_backwards_clock_never_reopens_a_tax_period():
    """Un reloj atrasado no devuelve dinero ni reabre días liquidados."""
    result = assess_tax(100, 100, DAY, DAY - 1, remainder=500)
    assert (result.wallet, result.bank, result.last_day, result.remainder) == (100, 100, DAY, 500)


@pytest.mark.parametrize(
    "values",
    [(-1, 0, DAY, DAY), (0, MAX_BANK_GOLD + 1, DAY, DAY), (True, 0, DAY, DAY), (0, 0, -1, DAY)],
)
def test_corrupt_fiscal_state_is_rejected(values):
    """No se normalizan silenciosamente saldos o fechas corruptos."""
    with pytest.raises(ValueError, match="fuera de rango"):
        assess_tax(*values)


async def prepare(redis_client):
    """Prepara dos cuentas y un período fiscal pendiente en el Redis descartable."""
    await redis_client.redis.hset(
        TAX_POLICY_KEY,
        mapping={"version": "1", "activation_day": str(DAY - 1), "rate_bps": "100", "enabled": "1"},
    )
    await redis_client.redis.hset(RedisKeys.player_user_stats(1), mapping={"gold": "1000"})
    await redis_client.redis.set(RedisKeys.bank_gold(1), "1000")
    await redis_client.redis.hset(tax_key(1), mapping={"version": "1", "last_day": str(DAY - 1)})


@pytest.mark.asyncio
async def test_tax_and_bank_transfer_share_one_commit(redis_client):
    """Depósito e impuesto conservan el mismo resultado al repetir el ID."""
    await prepare(redis_client)
    identity = operation_id()
    with patch("src.economy.taxes.utc_day", return_value=DAY):
        first = await transfer_gold(redis_client.redis, 1, 200, "deposit", identity)
        again = await transfer_gold(redis_client.redis, 1, 200, "deposit", identity)
    assert first == again
    assert (first["player_gold"], first["bank_gold"]) == (790, 1190)
    assert await redis_client.redis.hget(tax_key(1), "total_paid") == "20"


@pytest.mark.asyncio
async def test_concurrent_liquidators_charge_one_day_once(redis_client):
    """Cuatro liquidadores concurrentes cobran un único período."""
    await prepare(redis_client)
    resource = Resource(RedisKeys.player_user_stats(1), "hash")
    with patch("src.economy.taxes.utc_day", return_value=DAY):
        await asyncio.gather(
            *(
                transact(
                    redis_client.redis,
                    (resource,),
                    operation_id(),
                    {"bill": index},
                    lambda _: Decision({"applied": True}, {}),
                )
                for index in range(4)
            )
        )
    assert await redis_client.redis.hget(tax_key(1), "total_paid") == "20"
    assert await redis_client.redis.hget(RedisKeys.player_user_stats(1), "gold") == "990"
    assert await redis_client.redis.get(RedisKeys.bank_gold(1)) == "990"


@pytest.mark.asyncio
async def test_credit_settles_previous_days_before_adding_new_income(redis_client):
    """Los ingresos nuevos no pagan los días anteriores ni reinician el reloj."""
    await prepare(redis_client)
    identity = operation_id()
    with patch("src.economy.taxes.utc_day", return_value=DAY):
        first = await change_gold(
            redis_client.redis, RedisKeys.player_user_stats(1), 100, "credit", identity=identity
        )
        again = await change_gold(
            redis_client.redis, RedisKeys.player_user_stats(1), 100, "credit", identity=identity
        )
    assert first == again
    assert first.balance == 1090
    assert await redis_client.redis.hget(tax_key(1), "total_paid") == "20"


@pytest.mark.asyncio
async def test_business_rejection_does_not_roll_back_a_due_tax(redis_client):
    """El impuesto pendiente se liquida aunque se rechace un débito excesivo."""
    await prepare(redis_client)
    with patch("src.economy.taxes.utc_day", return_value=DAY):
        result = await change_gold(
            redis_client.redis, RedisKeys.player_user_stats(1), 1000, "debit"
        )
    assert not result.applied
    assert result.balance == 990
    assert await redis_client.redis.hget(tax_key(1), "last_day") == str(DAY)


@pytest.mark.asyncio
async def test_balances_share_a_monotonic_revision_across_tax_and_business(redis_client):
    """Impuesto e ingreso forman una revisión; repetir el ID no la incrementa."""
    await prepare(redis_client)
    identity = operation_id()
    with patch("src.economy.taxes.utc_day", return_value=DAY):
        await change_gold(
            redis_client.redis, RedisKeys.player_user_stats(1), 100, "credit", identity=identity
        )
        await change_gold(
            redis_client.redis, RedisKeys.player_user_stats(1), 100, "credit", identity=identity
        )
        assert await redis_client.redis.get(money_revision_key(1)) == "1"
        await transfer_gold(redis_client.redis, 1, 100, "deposit", operation_id())
    with patch("src.economy.tax_service.utc_day", return_value=DAY):
        status = await tax_status(redis_client.redis, 1)
    assert status["money_revision"] == 2
    assert (status["wallet"], status["bank"]) == (990, 1090)
