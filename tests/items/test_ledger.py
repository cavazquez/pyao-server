"""Propiedad individual, migración y desgaste bajo el mismo EXEC de negocio."""

import json
import time
from unittest.mock import AsyncMock, patch

import pytest

from src.economy.merchant_stock import StockEntry, restock_merchant, seed_merchant
from src.items.ledger import PREFIX
from src.items.migration import migrate
from src.items.view import pages
from src.models.items_catalog import ITEMS_CATALOG
from src.services.bank_item_transfer import transfer_bank_item
from src.services.ground_transfer import GroundRequest, transfer_ground
from src.services.npc_trade_plan import NpcTradePlan, NpcTradeRequest
from src.services.trade_settlement import OfferedItem, ParticipantOffer, settle_trade
from src.utils.gold_atomic import operation_id
from src.utils.ground_storage import read_ground
from src.utils.inventory_slot import InventorySlot
from src.utils.redis_config import RedisKeys
from src.utils.resource_transaction import Decision, Resource, transact


@pytest.mark.asyncio
async def test_migration_bank_and_retry_keep_identity_and_age(redis_client):
    """Depositar no vuelve a crear ni rejuvenece un objeto."""
    redis = redis_client.redis
    key, bank = RedisKeys.player_inventory(1), RedisKeys.bank(1)
    await redis.hset(key, mapping={"slot_1": "2:2"})
    await migrate(redis)
    assert json.loads(await redis.get("items:migration:backup:" + key)) == {"slot_1": "2:2"}
    first = InventorySlot.parse(await redis.hget(key, "slot_1"))
    second = InventorySlot.parse(await redis.hget(key, "slot_2"))
    assert first.quantity == second.quantity == 1
    assert first.instance_ids != second.instance_ids
    iid = first.instance_ids[0]
    original = await redis.hgetall(PREFIX + iid)
    assert await migrate(redis) == 0
    identity = operation_id()
    with patch("src.services.bank_item_transfer.require_durable", new=AsyncMock()):
        result = await transfer_bank_item(redis, 1, 1, 1, "deposit", identity)
        assert result["applied"]
        assert await transfer_bank_item(redis, 1, 1, 1, "deposit", identity) == result
    assert InventorySlot.parse(await redis.hget(bank, "slot_1")).instance_ids == (iid,)
    state = await redis.hgetall(PREFIX + iid)
    assert state["created_at"] == original["created_at"]
    assert state["expires_at"] == original["expires_at"]
    assert state["location"] == bank + "|slot_1"
    assert state["version"] == "2"


@pytest.mark.asyncio
async def test_wear_is_atomic_and_retry_does_not_spend_twice(redis_client):
    """El recibo resuelve el reintento sin cobrar usos nuevos."""
    redis = redis_client.redis
    key = RedisKeys.player_inventory(1)
    await redis.hset(key, "slot_1", "2:1")
    await migrate(redis)
    iid = InventorySlot.parse(await redis.hget(key, "slot_1")).instance_ids[0]
    identity = operation_id()

    def decide(_snapshot):
        return Decision({"applied": True, "_item_uses": {iid: 1}}, {})

    result = await transact(redis, (Resource(key, "hash"),), identity, {}, decide)
    assert "_item_uses" not in result
    assert await transact(redis, (Resource(key, "hash"),), identity, {}, decide) == result
    assert await redis.hget(PREFIX + iid, "uses_spent") == "1"


@pytest.mark.asyncio
async def test_duplicate_reference_rejected_before_mutation(redis_client):
    """La corrupción se rechaza antes del EXEC."""
    redis = redis_client.redis
    key = RedisKeys.player_inventory(1)
    await redis.hset(key, "slot_1", "2:1")
    await migrate(redis)
    value = await redis.hget(key, "slot_1")
    await redis.hset(key, "slot_2", value)
    with pytest.raises(ValueError, match="duplicada"):
        await transact(
            redis,
            (Resource(key, "hash"),),
            operation_id(),
            {},
            lambda _: Decision({}, {key: {"slot_1": ""}}),
        )
    assert await redis.hget(key, "slot_1") == value


@pytest.mark.asyncio
async def test_ground_cycle_preserves_spent_uses_and_age(redis_client):
    """Tirar y recoger no crea un ejemplar nuevo, incluso cuando ya está roto."""
    redis = redis_client.redis
    key = RedisKeys.player_inventory(1)
    await redis.hset(key, "slot_1", "2:1")
    await redis.hset(RedisKeys.player_position(1), mapping={"map": 1, "x": 50, "y": 50})
    await redis.hset(RedisKeys.player_user_stats(1), mapping={"min_hp": 100, "gold": 100})
    await migrate(redis)
    iid = InventorySlot.parse(await redis.hget(key, "slot_1")).instance_ids[0]
    await redis.hset(PREFIX + iid, "uses_spent", "10000")
    original = await redis.hgetall(PREFIX + iid)
    with patch("src.services.ground_transfer.require_durable", new=AsyncMock()):
        result = await transfer_ground(
            redis,
            GroundRequest(1, 1, 50, 50, "drop_item", slot=1, quantity=1, expected_item_id=2),
            operation_id(),
        )
        assert result["applied"]
        tile = (await read_ground(redis, 1)).tile(50, 50)
        assert tile[0]["instance_ids"] == [iid]
        result = await transfer_ground(
            redis,
            GroundRequest(1, 1, 50, 50, "pickup", expected_stack=tile[0]["stack_id"]),
            operation_id(),
        )
        assert result["applied"]
    restored = await redis.hgetall(PREFIX + iid)
    assert restored["created_at"] == original["created_at"]
    assert restored["expires_at"] == original["expires_at"]
    assert restored["uses_spent"] == "10000"
    assert InventorySlot.parse(await redis.hget(key, "slot_1")).instance_ids == (iid,)


@pytest.mark.asyncio
async def test_trade_same_type_swaps_the_actual_instances(redis_client):
    """Un intercambio bidireccional de espadas iguales no retiene la espada equivocada."""
    redis = redis_client.redis
    for user in (1, 2):
        await redis.hset(RedisKeys.player_inventory(user), "slot_1", "2:1")
    await migrate(redis)
    original = [
        InventorySlot.parse(
            await redis.hget(RedisKeys.player_inventory(user), "slot_1")
        ).instance_ids
        for user in (1, 2)
    ]
    with patch("src.services.trade_settlement.require_durable", new=AsyncMock()):
        result = await settle_trade(
            redis,
            operation_id(),
            tuple(ParticipantOffer(user, 0, (OfferedItem(1, 2, 1),)) for user in (1, 2)),
            30,
            20,
        )
    assert result["applied"]
    for user in (1, 2):
        assert (
            InventorySlot.parse(
                await redis.hget(RedisKeys.player_inventory(user), "slot_1")
            ).instance_ids
            == original[2 - user]
        )


@pytest.mark.asyncio
async def test_view_distinguishes_two_worn_instances_and_expiry(redis_client):
    """La UI recibe base/efectivo por ejemplar y páginas menores al límite de red."""
    redis = redis_client.redis
    key = RedisKeys.player_inventory(1)
    await redis.hset(key, "slot_1", "2:2")
    await migrate(redis)
    second = InventorySlot.parse(await redis.hget(key, "slot_2")).instance_ids[0]
    await redis.hset(
        PREFIX + second, mapping={"uses_spent": "10000", "expires_at": str(int(time.time()) - 1)}
    )
    result = await pages(redis, {"inventory": (key, tuple(range(1, 31)))})
    assert len(result) == 6
    first, other = result[0]["rows"][0][1], result[0]["rows"][1][1]
    assert first["id"] != other["id"]
    assert not first["broken"]
    assert other["broken"]
    assert all(value == 0 for value in other["effective"].values())
    assert all(len(json.dumps(page)) < 3500 for page in result)


@pytest.mark.asyncio
async def test_full_legacy_bag_stops_migration_without_losing_units(redis_client):
    """La migración conserva el original y la época al reanudar tras liberar espacio."""
    redis = redis_client.redis
    key = RedisKeys.player_inventory(1)
    original = {f"slot_{slot}": "1:1" for slot in range(1, 31)}
    original["slot_1"] = "2:2"
    await redis.hset(key, mapping=original)
    with pytest.raises(ValueError, match="liberá slots"):
        await migrate(redis)
    epoch = await redis.get("items:migration:epoch")
    assert await redis.hgetall(key) == original
    assert not await redis.exists("items:format_version")
    await redis.hset(key, "slot_2", "")
    await migrate(redis)
    first = InventorySlot.parse(await redis.hget(key, "slot_1"))
    second = InventorySlot.parse(await redis.hget(key, "slot_2"))
    assert first.quantity == second.quantity == 1
    assert await redis.hget(PREFIX + first.instance_ids[0], "created_at") == epoch
    assert await redis.hget(PREFIX + second.instance_ids[0], "created_at") == epoch


@pytest.mark.asyncio
async def test_merchant_sale_buyback_and_restock_keep_old_instances(redis_client):
    """La reposición agrega ejemplares nuevos sin reparar los revendidos."""
    redis = redis_client.redis
    key, stock = RedisKeys.player_inventory(1), RedisKeys.merchant_inventory(7)
    await redis.hset(key, "slot_1", "2:1")
    await redis.hset(RedisKeys.player_user_stats(1), "gold", "1000000")
    await seed_merchant(redis, 7, (StockEntry(2, 3, 1),), now=100)
    await migrate(redis)
    iid = InventorySlot.parse(await redis.hget(key, "slot_1")).instance_ids[0]
    await redis.hset(PREFIX + iid, "uses_spent", "5000")
    resources = (
        Resource(key, "hash"),
        Resource(stock, "hash"),
        Resource(RedisKeys.player_equipment(1), "hash"),
        Resource(RedisKeys.player_user_stats(1), "hash"),
        Resource("merchant:7:items", "set"),
    )

    async def trade(action, slot):
        request = NpcTradeRequest(1, 7, slot, 1, action)
        result = await transact(
            redis,
            resources,
            operation_id(),
            {"trade": action, "slot": slot},
            lambda snapshot: NpcTradePlan(snapshot, request, 30, 20, 20).decide(ITEMS_CATALOG, 2),
        )
        assert result["applied"]

    await trade("sell", 1)
    ids = InventorySlot.parse(await redis.hget(stock, "slot_1")).instance_ids
    assert iid in ids
    # Comprar los ejemplares previos y luego el mismo revendido.
    for _ in range(4):
        await trade("buy", 1)
    assert iid in {
        identity
        for value in (await redis.hgetall(key)).values()
        if (slot := InventorySlot.parse(value))
        for identity in slot.instance_ids
    }
    assert await redis.hget(PREFIX + iid, "uses_spent") == "5000"
    await restock_merchant(redis, 7, now=3700)
    fresh = InventorySlot.parse(await redis.hget(stock, "slot_1"))
    assert fresh.quantity == 1
    assert iid not in fresh.instance_ids


@pytest.mark.asyncio
async def test_migration_refuses_active_players_without_touching_their_items(redis_client):
    """Una actualización no transforma el formato debajo de sesiones antiguas activas."""
    redis = redis_client.redis
    await redis.set("session:1:owner", "active")
    await redis.hset(RedisKeys.player_inventory(1), "slot_1", "2:2")
    with pytest.raises(RuntimeError, match="sesiones activas"):
        await migrate(redis)
    assert await redis.hget(RedisKeys.player_inventory(1), "slot_1") == "2:2"
    assert not await redis.exists("items:format_version")
