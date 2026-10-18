"""Comercio NPC con recursos reales: última unidad, pagos exactos y fallas de EXEC."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from redis.exceptions import ConnectionError as RedisConnectionError

from src.models.item import Item, ItemType
from src.models.item_constants import MAX_PLAYER_GOLD
from src.repositories.inventory_repository import InventoryRepository
from src.repositories.merchant_repository import MerchantRepository
from src.repositories.player_repository import PlayerRepository
from src.services.commerce_service import CommerceService
from src.utils.gold_atomic import operation_id
from src.utils.redis_config import RedisKeys


@pytest_asyncio.fixture
async def market(redis_client):
    """Comparte recursos concretos y sustituye sólo fsync en tests rápidos.

    Yields:
        Servicio, inventario, jugador y Redis con una poción de valor impar.
    """
    item = Item(
        item_id=1,
        name="Poción",
        item_type=ItemType.POTION,
        graphic_id=100,
        value=11,
        stackable=True,
    )
    inventory, player = InventoryRepository(redis_client), PlayerRepository(redis_client)
    await player.update_gold(1, 100)
    await player.update_gold(2, 100)
    await inventory.set_slot(1, 30, 1, 5)
    await redis_client.hset(RedisKeys.merchant_inventory(123), mapping={"slot_1": "1:5"})
    service = CommerceService(inventory, MerchantRepository(redis_client), {1: item}, player)
    with patch("src.services.commerce_service.require_durable", new=AsyncMock()):
        yield service, inventory, player, redis_client


@pytest.mark.asyncio
async def test_buy_and_odd_sell_are_identified_and_exact(market):
    """Repetir una petición no vuelve a comprar ni a pagar; 11//2 por tres es quince."""
    service, inventory, player, redis = market
    buy_id, sell_id = operation_id(), operation_id()
    for _ in range(2):
        assert (await service.buy_item(1, 123, 1, 1, operation_id=buy_id))[0]
    assert await player.get_gold(1) == 89
    assert await inventory.get_slot(1, 30) == (1, 6)
    for _ in range(2):
        success, message = await service.sell_item(1, 123, 30, 3, operation_id=sell_id)
        assert success
        assert "15 oro" in message
    assert await player.get_gold(1) == 104
    assert await inventory.get_slot(1, 30) == (1, 3)
    assert (await redis.hgetall(RedisKeys.merchant_inventory(123)))["slot_1"] == "1:7"


@pytest.mark.asyncio
async def test_two_buyers_compete_for_last_unit_without_double_debit(market):
    """WATCH del stock serializa compras aunque los jugadores tengan distintas claves."""
    service, inventory, player, redis = market
    await redis.hset(RedisKeys.merchant_inventory(123), mapping={"slot_1": "1:1"})
    results = await asyncio.gather(service.buy_item(1, 123, 1, 1), service.buy_item(2, 123, 1, 1))
    assert sum(success for success, _message in results) == 1
    assert await player.get_gold(1) + await player.get_gold(2) == 189
    inventories = await asyncio.gather(*(inventory.get_inventory_slots(user) for user in [1, 2]))
    total = sum(stack.quantity for values in inventories for stack in values.values())
    assert total == 6
    assert not (await redis.hgetall(RedisKeys.merchant_inventory(123)))["slot_1"]


@pytest.mark.asyncio
async def test_competing_sales_pay_for_source_once(market):
    """Dos ventas de tres unidades compiten por cinco; una sola cobra quince."""
    service, inventory, player, _redis = market
    results = await asyncio.gather(
        service.sell_item(1, 123, 30, 3), service.sell_item(1, 123, 30, 3)
    )
    assert sum(success for success, _message in results) == 1
    assert await player.get_gold(1) == 115
    assert await inventory.get_slot(1, 30) == (1, 2)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "case",
    ["full", "partial", "overflow", "excess_buy", "excess_sell", "negative", "price", "equipment"],
)
async def test_rejection_preserves_stock_wallet_and_inventory(market, case):
    """Un rechazo conserva los tres recursos completos, incluido espacio parcial insuficiente."""
    service, inventory, player, redis = market
    action, slot, quantity = service.buy_item, 1, 1
    if case in {"full", "partial"}:
        for index in range(1, 31):
            await inventory.set_slot(1, index, 2, 20)
        if case == "partial":
            await inventory.set_slot(1, 30, 1, 19)
            quantity = 2
    elif case == "overflow":
        action, slot = service.sell_item, 30
        await player.update_gold(1, MAX_PLAYER_GOLD)
    elif case == "excess_buy":
        quantity = 6
    elif case == "excess_sell":
        action, slot, quantity = service.sell_item, 30, 6
    elif case == "negative":
        quantity = -1
    elif case == "price":
        service.items_catalog[1].value = -1
    else:
        action, slot = service.sell_item, 30
        await redis.hset(RedisKeys.player_equipment(1), mapping={"weapon": "30"})
    before = (
        await inventory.get_inventory(1),
        await player.get_gold(1),
        await redis.hgetall(RedisKeys.merchant_inventory(123)),
    )
    assert not (await action(1, 123, slot, quantity))[0]
    assert (
        await inventory.get_inventory(1),
        await player.get_gold(1),
        await redis.hgetall(RedisKeys.merchant_inventory(123)),
    ) == before


@pytest.mark.asyncio
async def test_full_merchant_keeps_prior_buyback_policy_without_partial_stock(market):
    """El NPC paga aunque no guarde el objeto para revender; no añade medio stack."""
    service, inventory, player, redis = market
    await redis.hset(
        RedisKeys.merchant_inventory(123), mapping={f"slot_{i}": "2:32767" for i in range(1, 21)}
    )
    await redis.hset(RedisKeys.merchant_inventory(123), mapping={"slot_1": "1:32766"})
    before = await redis.hgetall(RedisKeys.merchant_inventory(123))
    assert (await service.sell_item(1, 123, 30, 3))[0]
    assert await player.get_gold(1) == 115
    assert await inventory.get_slot(1, 30) == (1, 2)
    assert await redis.hgetall(RedisKeys.merchant_inventory(123)) == before


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["buy", "sell"])
@pytest.mark.parametrize("after_exec", [False, True])
async def test_exec_failure_recovers_identified_result_without_partial_resources(
    market, action, after_exec
):
    """Cortes a ambos lados de EXEC no separan débito, stock y entrega o pago."""
    service, inventory, player, redis = market
    pipeline_type = type(redis.redis.pipeline())
    original = pipeline_type.execute
    failed_once = False

    async def faulty_exec(self, *args: object, **kwargs: object):
        nonlocal failed_once
        if failed_once:
            return await original(self, *args, **kwargs)
        failed_once = True
        if after_exec:
            await original(self, *args, **kwargs)
        message = "Falla simulada de EXEC en comercio"
        raise RedisConnectionError(message)

    identity = operation_id()
    method, slot = (service.buy_item, 1) if action == "buy" else (service.sell_item, 30)
    with patch.object(pipeline_type, "execute", faulty_exec):
        assert (await method(1, 123, slot, 3, operation_id=identity))[0]
    assert (await method(1, 123, slot, 3, operation_id=identity))[0]
    assert await player.get_gold(1) == (67 if action == "buy" else 115)
    assert await inventory.get_slot(1, 30) == (1, 8 if action == "buy" else 2)


@pytest.mark.asyncio
async def test_purchase_replans_when_gain_and_equipped_drag_commit_first(market):
    """Un plan de compra ya calculado no pisa ganancias ni un MOVE_ITEM concurrente."""
    service, inventory, player, redis = market
    await inventory.set_slot(1, 1, 2, 1)
    await redis.hset(RedisKeys.player_equipment(1), mapping={"weapon": "1"})
    pipeline_type = type(redis.redis.pipeline())
    original = pipeline_type.execute
    entered, resume = asyncio.Event(), asyncio.Event()
    first = True

    async def pause_exec(self, *args: object, **kwargs: object):
        nonlocal first
        if first:
            first = False
            entered.set()
            await resume.wait()
        return await original(self, *args, **kwargs)

    with patch.object(pipeline_type, "execute", pause_exec):
        purchase = asyncio.create_task(service.buy_item(1, 123, 1, 1))
        await asyncio.wait_for(entered.wait(), 2)
        assert await inventory.add_item(1, 1, 2)
        assert (await inventory.swap_slots(1, 1, 30)).success
        resume.set()
        assert (await asyncio.wait_for(purchase, 2))[0]
    assert await inventory.get_slot(1, 1) == (1, 8)
    assert await inventory.get_slot(1, 30) == (2, 1)
    assert (await redis.hgetall(RedisKeys.player_equipment(1)))["weapon"] == "30"
    assert await player.get_gold(1) == 89
