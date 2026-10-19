"""Devaluación del suelo, cruces del corte y conservación de fracciones al mover oro."""

import asyncio
import json
from unittest.mock import AsyncMock, patch

import pytest
from redis.exceptions import ConnectionError as RedisConnectionError

from src.economy.ground_devaluation import settle_ground_gold
from src.economy.maintenance import EconomyMaintenance
from src.economy.tax_service import settle_user_taxes
from src.economy.tax_transactions import tax_key
from src.economy.taxes import TAX_POLICY_KEY
from src.game.ground_item_index import GroundItemIndex
from src.models.item_constants import GOLD_ITEM_ID, MAX_PLAYER_GOLD
from src.repositories.ground_items_repository import GroundItemsRepository
from src.services.ground_transfer import GroundRequest, transfer_ground
from src.services.player.lifecycle import settle_death
from src.services.trade_settlement import ParticipantOffer, settle_trade
from src.utils.gold_atomic import operation_id
from src.utils.ground_state import GroundState, stack_identity
from src.utils.redis_config import RedisKeys

DAY = 20_000


@pytest.fixture(autouse=True)
def clock():
    """Controla cortes, no la edad de los IDs; sustituye sólo fsync del Redis fake.

    Yields:
        Día del servidor modificable por el escenario.
    """
    day = [DAY]
    with (
        patch("src.economy.taxes.utc_day", side_effect=lambda: day[0]),
        patch("src.economy.ground_devaluation.utc_day", side_effect=lambda: day[0]),
        patch("src.economy.tax_service.utc_day", side_effect=lambda: day[0]),
        patch("src.economy.ground_devaluation.require_durable", new=AsyncMock()),
        patch("src.economy.tax_service.require_durable", new=AsyncMock()),
        patch("src.services.ground_transfer.require_durable", new=AsyncMock()),
        patch("src.services.player.lifecycle.require_durable", new=AsyncMock()),
        patch("src.repositories.ground_items_repository.require_durable", new=AsyncMock()),
    ):
        yield day


async def prepare(redis, user=1, gold=1000, bank=0, remainder=0, day=DAY):
    """Prepara saldos y marcadores ya liquidados al inicio del ensayo."""
    await redis.hset(
        TAX_POLICY_KEY,
        mapping={
            "version": "1",
            "enabled": "1",
            "rate_bps": "100",
            "activation_day": str(DAY),
            "ground_activation_day": str(DAY),
        },
    )
    await redis.hset(
        RedisKeys.player_user_stats(user), mapping={"gold": str(gold), "min_hp": "100"}
    )
    await redis.set(RedisKeys.bank_gold(user), str(bank))
    await redis.hset(RedisKeys.player_position(user), mapping={"map": "1", "x": "50", "y": "50"})
    await redis.hset(
        tax_key(user),
        mapping={
            "version": "1",
            "last_day": str(day),
            "remainder": str(remainder),
            "total_paid": "0",
        },
    )


async def drop(redis, quantity=1000, user=1):
    """Tira oro por el mismo servicio que usa el comando real.

    Returns:
        Identidad del montón creado en la operación confirmada.
    """
    result = await transfer_ground(
        redis, GroundRequest(user, 1, 50, 50, "drop_gold", quantity=quantity), operation_id()
    )
    assert result["applied"], result
    return result["item"]["stack_id"]


async def pickup(redis, stack, user=1, identity=None):
    """Recoge por identidad, sin modificar datos entre lectura y commit.

    Returns:
        Resultado del servicio de suelo real.
    """
    return await transfer_ground(
        redis,
        GroundRequest(user, 1, 50, 50, "pickup", expected_stack=stack),
        identity or operation_id(),
    )


async def rows(redis):
    """Lee el suelo persistido.

    Returns:
        Lista de montones del tile de prueba.
    """
    return GroundState(1, await redis.get(RedisKeys.ground_items(1))).tile(50, 50)


@pytest.mark.asyncio
@pytest.mark.parametrize("collector", [1, 2])
async def test_drop_before_cutoff_pickup_after_devalues_once(redis_client, clock, collector):
    """El mismo jugador u otro recupera 990, nunca 1000 ni 980."""
    redis = redis_client.redis
    await prepare(redis)
    await prepare(redis, user=2, gold=0)
    stack = await drop(redis)
    clock[0] += 1
    await settle_user_taxes(redis, 1)
    await settle_ground_gold(redis, 1)
    await settle_ground_gold(redis, 1)
    identity = operation_id()
    result = await pickup(redis, stack, collector, identity)
    assert result["applied"]
    assert result["quantity"] == 990
    assert await pickup(redis, stack, collector, identity) == result
    assert await redis.hget(RedisKeys.player_user_stats(collector), "gold") == "990"
    assert not await rows(redis)


@pytest.mark.asyncio
async def test_same_day_and_repeated_drop_preserve_fraction(redis_client, clock):
    """Tirar y recoger no genera un día nuevo ni borra la fracción acumulada."""
    redis = redis_client.redis
    await prepare(redis, gold=1, remainder=9800)
    stack = await drop(redis, 1)
    assert (await rows(redis))[0]["devaluation_remainder"] == 9800
    result = await pickup(redis, stack)
    assert result["quantity"] == 1
    assert await redis.hget(tax_key(1), "remainder") == "9800"
    stack = await drop(redis, 1)
    clock[0] += 1
    assert (await pickup(redis, stack))["applied"]
    assert await redis.hget(tax_key(1), "remainder") == "9900"
    stack = await drop(redis, 1)
    clock[0] += 1
    assert not (await pickup(redis, stack))["applied"]
    assert await redis.hget(RedisKeys.player_user_stats(1), "gold") == "0"
    assert not await rows(redis)


@pytest.mark.asyncio
async def test_partial_pickup_keeps_fraction_and_finalizes_accumulated_coin(redis_client):
    """Una recogida parcial reparte fracciones y materializa una moneda ya acumulada."""
    redis = redis_client.redis
    await prepare(redis, gold=MAX_PLAYER_GOLD - 5, remainder=6000)
    item = {
        "item_id": GOLD_ITEM_ID,
        "quantity": 10,
        "stack_id": stack_identity("partial"),
        "devaluation_day": DAY,
        "devaluation_remainder": 9000,
    }
    await redis.set(RedisKeys.ground_items(1), json.dumps({"50,50": [item]}))
    result = await pickup(redis, item["stack_id"])
    assert result["quantity"] == 5
    assert result["devaluation_loss"] == 1
    assert await redis.hget(RedisKeys.player_user_stats(1), "gold") == str(MAX_PLAYER_GOLD - 1)
    assert await redis.hget(tax_key(1), "remainder") == "500"
    assert await redis.hget(tax_key(1), "total_paid") == "1"
    remaining = (await rows(redis))[0]
    assert (remaining["quantity"], remaining["devaluation_remainder"]) == (5, 4500)


@pytest.mark.asyncio
async def test_worker_devalues_without_players_and_preserves_ttl(redis_client, clock):
    """El mantenimiento no depende de sesiones ni prolonga la vida de los objetos."""
    redis = redis_client.redis
    await prepare(redis)
    await drop(redis)
    await redis.pexpire(RedisKeys.ground_items(1), 500_000)
    before = await redis.pttl(RedisKeys.ground_items(1))
    clock[0] += 1
    worker = EconomyMaintenance(redis)
    await worker._sweep("ground_items:*", worker.ground_action)
    await worker._sweep("ground_items:*", worker.ground_action)
    assert (await rows(redis))[0]["quantity"] == 990
    assert 0 < await redis.pttl(RedisKeys.ground_items(1)) <= before


@pytest.mark.asyncio
async def test_legacy_gold_adopts_activation_without_retroactive_loss(redis_client, clock):
    """Los montones anteriores empiezan en la activación; lo nuevo empieza al generarse."""
    redis = redis_client.redis
    await prepare(redis)
    await redis.set(
        RedisKeys.ground_items(1),
        json.dumps({"50,50": [{"item_id": GOLD_ITEM_ID, "quantity": 1000}]}),
    )
    await settle_ground_gold(redis, 1)
    assert (await rows(redis))[0]["quantity"] == 1000
    clock[0] += 1
    await settle_ground_gold(redis, 1)
    assert (await rows(redis))[0]["quantity"] == 990
    clock[0] += 4
    repo = GroundItemsRepository(redis_client)
    result = await repo.add_ground_item(1, 51, 50, {"item_id": GOLD_ITEM_ID, "quantity": 1000})
    assert result["applied"]
    created = (await repo.load_ground_items(1))[51, 50][0]
    assert (created["quantity"], created["devaluation_day"]) == (1000, clock[0])


@pytest.mark.asyncio
async def test_two_collectors_cannot_duplicate_devalued_stack(redis_client, clock):
    """Ambos observan el mismo montón pero sólo uno acredita las 990 monedas."""
    redis = redis_client.redis
    await prepare(redis)
    await prepare(redis, user=2, gold=0)
    stack = await drop(redis)
    clock[0] += 1
    results = await asyncio.gather(pickup(redis, stack, 1), pickup(redis, stack, 2))
    assert sum(result["applied"] for result in results) == 1
    balances = [int(await redis.hget(RedisKeys.player_user_stats(user), "gold")) for user in (1, 2)]
    assert sum(balances) == 990
    assert not await rows(redis)


@pytest.mark.asyncio
async def test_lost_exec_ack_keeps_devaluation_and_credit_together(redis_client, clock):
    """Una caída posterior al commit recupera el resultado sin volver a descontar."""
    redis = redis_client.redis
    await prepare(redis)
    stack = await drop(redis)
    clock[0] += 1
    pipeline_type = type(redis.pipeline())
    execute = pipeline_type.execute
    lost = False

    async def uncertain(pipe, *args: object, **kwargs: object):
        nonlocal lost
        result = await execute(pipe, *args, **kwargs)
        if not lost:
            lost = True
            message = "ACK perdido del commit de suelo"
            raise RedisConnectionError(message)
        return result

    with patch.object(pipeline_type, "execute", uncertain):
        result = await pickup(redis, stack)
    assert result["applied"]
    assert result["quantity"] == 990
    assert await redis.hget(RedisKeys.player_user_stats(1), "gold") == "990"
    assert not await rows(redis)


@pytest.mark.asyncio
async def test_death_drop_carries_its_fraction(redis_client):
    """Morir mueve oro y fracciones en el mismo commit que la penalización."""
    redis = redis_client.redis
    await prepare(redis, remainder=9000)
    await redis.hset(
        RedisKeys.player_user_stats(1),
        mapping={
            "min_hp": "0",
            "death_state": "pending",
            "life_id": "1",
            "death_event": "devaluation-death",
        },
    )
    result = await settle_death(redis, 1, 1, 1, 50, 50)
    assert result["gold_drop"] == 100
    item = (await rows(redis))[0]
    assert (item["quantity"], item["devaluation_remainder"], item["devaluation_day"]) == (
        100,
        900,
        DAY,
    )
    assert await redis.hget(tax_key(1), "remainder") == "8100"


@pytest.mark.asyncio
async def test_last_coin_disappears_from_loaded_map(redis_client, clock):
    """Al agotarse un montón se retira de Redis, la caché y ambos clientes del mapa."""
    redis = redis_client.redis
    await prepare(redis, gold=1, remainder=9900)
    await drop(redis, 1)
    index = GroundItemIndex(10, GroundItemsRepository(redis_client))
    await index.load_ground_items(1)
    assert index.get_ground_items(1, 50, 50)
    clock[0] += 1
    broadcast = AsyncMock()
    await index.settle_devaluation(1, broadcast)
    assert not index.get_ground_items(1, 50, 50)
    assert not await rows(redis)
    broadcast.broadcast_object_delete.assert_awaited_once_with(1, 50, 50)
    broadcast.broadcast_object_create.assert_not_awaited()


@pytest.mark.asyncio
async def test_multiple_missed_days_match_consecutive_daily_settlements(redis_client, clock):
    """El servidor apagado conserva la misma secuencia diaria del montón."""
    redis = redis_client.redis
    await prepare(redis)
    await drop(redis)
    original = await redis.get(RedisKeys.ground_items(1))
    clock[0] += 3
    await settle_ground_gold(redis, 1)
    offline = await rows(redis)
    assert (offline[0]["quantity"], offline[0]["devaluation_remainder"]) == (971, 7100)
    await redis.set(RedisKeys.ground_items(1), original)
    for day in range(DAY + 1, DAY + 4):
        clock[0] = day
        await settle_ground_gold(redis, 1)
    assert await rows(redis) == offline


@pytest.mark.asyncio
async def test_worker_isolates_corrupt_map(redis_client, clock):
    """Un JSON con estructura inválida no mata el barrido de los demás mapas."""
    redis = redis_client.redis
    await prepare(redis)
    await drop(redis)
    await redis.set(RedisKeys.ground_items(2), "[]")
    clock[0] += 1
    worker = EconomyMaintenance(redis)
    await worker._sweep("ground_items:*", worker.ground_action)
    assert (await rows(redis))[0]["quantity"] == 990
    assert await redis.get(RedisKeys.ground_items(2)) == "[]"


@pytest.mark.asyncio
async def test_failed_ground_notification_retries_after_cache_refresh(redis_client, clock):
    """Un envío fallido no deja visible para siempre un montón ya agotado."""
    redis = redis_client.redis
    await prepare(redis, gold=1, remainder=9900)
    await drop(redis, 1)
    index = GroundItemIndex(10, GroundItemsRepository(redis_client))
    await index.load_ground_items(1)
    clock[0] += 1
    broadcast = AsyncMock()
    broadcast.broadcast_object_delete.side_effect = ConnectionError()
    with pytest.raises(ConnectionError):
        await index.settle_devaluation(1, broadcast)
    broadcast.broadcast_object_delete.side_effect = None
    await index.settle_devaluation(1, broadcast)
    assert broadcast.broadcast_object_delete.await_count == 2
    assert not index.get_ground_items(1, 50, 50)


@pytest.mark.asyncio
async def test_trading_gold_cannot_reset_accumulated_fraction(redis_client, clock):
    """Cambiar una moneda de personaje cada día no borra su devaluación pendiente."""
    redis = redis_client.redis
    await prepare(redis, gold=1, remainder=9800)
    await prepare(redis, user=2, gold=0)
    with patch("src.services.trade_settlement.require_durable", new=AsyncMock()):
        first = await settle_trade(
            redis, operation_id(), (ParticipantOffer(1, 1, ()), ParticipantOffer(2, 0, ())), 30, 20
        )
        assert first["applied"]
        assert await redis.hget(tax_key(2), "remainder") == "9800"
        clock[0] += 1
        await settle_user_taxes(redis, 2)
        assert await redis.hget(tax_key(2), "remainder") == "9900"
        second = await settle_trade(
            redis, operation_id(), (ParticipantOffer(1, 0, ()), ParticipantOffer(2, 1, ())), 30, 20
        )
        assert second["applied"]
    assert await redis.hget(tax_key(1), "remainder") == "9900"
    clock[0] += 1
    await settle_user_taxes(redis, 1)
    assert await redis.hget(RedisKeys.player_user_stats(1), "gold") == "0"
    assert await redis.hget(RedisKeys.player_user_stats(2), "gold") == "0"


@pytest.mark.asyncio
async def test_trade_fraction_merge_charges_one_coin_once(redis_client):
    """Dos fracciones que completan una moneda se reducen en el mismo commit del trade."""
    redis = redis_client.redis
    await prepare(redis, gold=100, remainder=9000)
    await prepare(redis, user=2, gold=100, remainder=8000)
    identity = operation_id()
    offers = (ParticipantOffer(1, 100, ()), ParticipantOffer(2, 0, ()))
    with patch("src.services.trade_settlement.require_durable", new=AsyncMock()):
        result = await settle_trade(redis, identity, offers, 30, 20)
        assert result["applied"]
        assert await settle_trade(redis, identity, offers, 30, 20) == result
    assert await redis.hget(RedisKeys.player_user_stats(1), "gold") == "0"
    assert await redis.hget(RedisKeys.player_user_stats(2), "gold") == "199"
    assert await redis.hget(tax_key(1), "remainder") == "0"
    assert await redis.hget(tax_key(2), "remainder") == "7000"
    assert await redis.hget(tax_key(2), "total_paid") == "1"
