"""Conservación del stock y reposición ante reinicios y concurrencia."""

import asyncio

import pytest

from src.economy.maintenance import EconomyMaintenance
from src.economy.merchant_stock import StockEntry, catalog_key, restock_merchant, seed_merchant
from src.utils.redis_config import RedisKeys


@pytest.mark.asyncio
async def test_reloading_catalog_preserves_stock_and_player_resales(redis_client):
    """Un catálogo repetido no restaura unidades agotadas ni borra reventas."""
    redis = redis_client.redis
    entries = (StockEntry(15, 1000, 100),)
    await seed_merchant(redis, 7, entries, now=10000)
    await redis.hset(RedisKeys.merchant_inventory(7), mapping={"slot_1": "15:1", "slot_2": "139:3"})
    await seed_merchant(redis, 7, entries, now=10000)
    assert await redis.hget(RedisKeys.merchant_inventory(7), "slot_1") == "15:1"
    assert await redis.hget(RedisKeys.merchant_inventory(7), "slot_2") == "139:3"


@pytest.mark.asyncio
async def test_two_restockers_apply_one_interval_once(redis_client):
    """Dos workers concurrentes agregan sólo las unidades del período vencido."""
    redis = redis_client.redis
    await seed_merchant(redis, 7, (StockEntry(15, 1000, 100),), now=10000)
    await redis.hset(RedisKeys.merchant_inventory(7), "slot_1", "15:1")
    added = await asyncio.gather(*(restock_merchant(redis, 7, now=13600) for _ in range(2)))
    assert sum(added) == 100
    assert await redis.hget(RedisKeys.merchant_inventory(7), "slot_1") == "15:101"
    assert await redis.hget(catalog_key(7), "last_restock") == "13600"


@pytest.mark.asyncio
async def test_offline_restock_is_capped_without_trimming_player_surplus(redis_client):
    """Un apagado no supera topes ni recorta unidades vendidas por jugadores."""
    redis = redis_client.redis
    await seed_merchant(redis, 7, (StockEntry(15, 1000, 100), StockEntry(2, 1, 0)), now=10000)
    await redis.hset(RedisKeys.merchant_inventory(7), mapping={"slot_1": "15:0", "slot_2": "2:2"})
    # Un slot retirado queda vacío: cantidades cero no se persisten como objetos.
    await redis.hset(RedisKeys.merchant_inventory(7), "slot_1", "")
    assert await restock_merchant(redis, 7, now=10000 + 3600 * 1000) == 1000
    stock = await redis.hgetall(RedisKeys.merchant_inventory(7))
    assert "15:1000" in stock.values()
    assert "2:2" in stock.values()


@pytest.mark.asyncio
async def test_catalog_change_requires_explicit_migration_and_keeps_units(redis_client):
    """Cambiar el seed no se confunde con una reposición ni una limpieza."""
    redis = redis_client.redis
    await seed_merchant(redis, 7, (StockEntry(15, 1000, 100),))
    await seed_merchant(redis, 7, (StockEntry(15, 2000, 200),))
    assert "[15,1000,100]" in await redis.hget(catalog_key(7), "items")
    await seed_merchant(redis, 7, (StockEntry(15, 2000, 200),), replace_catalog=True)
    assert await redis.hget(RedisKeys.merchant_inventory(7), "slot_1") == "15:1000"


@pytest.mark.asyncio
async def test_empty_existing_merchant_is_never_reseeded(redis_client):
    """Agotar todos los slots no convierte al mercader en un catálogo nuevo."""
    redis = redis_client.redis
    await seed_merchant(redis, 7, (StockEntry(15, 1000, 100),))
    await redis.delete(RedisKeys.merchant_inventory(7))
    await seed_merchant(redis, 7, (StockEntry(15, 2000, 200),))
    assert not await redis.exists(RedisKeys.merchant_inventory(7))
    assert "[15,1000,100]" in await redis.hget(catalog_key(7), "items")


@pytest.mark.asyncio
async def test_two_initializers_do_not_overwrite_legacy_stock(redis_client):
    """La primera adopción de stock antiguo no borra sus cantidades ni reventas."""
    redis = redis_client.redis
    await redis.hset(RedisKeys.merchant_inventory(7), mapping={"slot_1": "139:5"})
    await asyncio.gather(*(seed_merchant(redis, 7, (StockEntry(15, 1000, 100),)) for _ in range(2)))
    assert await redis.hgetall(RedisKeys.merchant_inventory(7)) == {"slot_1": "139:5"}


@pytest.mark.asyncio
async def test_full_merchant_does_not_remove_player_resales_for_restock(redis_client):
    """Si no hay lugar se conserva cada reventa y no se crea stock parcial."""
    redis = redis_client.redis
    await seed_merchant(redis, 7, (StockEntry(15, 1000, 100),), now=10000)
    stock = {f"slot_{slot}": f"{100 + slot}:1" for slot in range(1, 21)}
    await redis.hset(RedisKeys.merchant_inventory(7), mapping=stock)
    assert await restock_merchant(redis, 7, now=13600) == 0
    assert await redis.hgetall(RedisKeys.merchant_inventory(7)) == stock


@pytest.mark.asyncio
async def test_catalog_migration_is_versioned_without_restock(redis_client):
    """La migración repetida conserva revisión, cantidades y último corte."""
    redis = redis_client.redis
    await seed_merchant(redis, 7, (StockEntry(15, 1000, 100),), now=10000)
    await redis.hset(RedisKeys.merchant_inventory(7), "slot_1", "15:5")
    for _ in range(2):
        await seed_merchant(redis, 7, (StockEntry(15, 2000, 200),), replace_catalog=True)
    assert await redis.hget(catalog_key(7), "revision") == "2"
    assert await redis.hget(catalog_key(7), "last_restock") == "10000"
    assert await redis.hget(RedisKeys.merchant_inventory(7), "slot_1") == "15:5"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "corrupt", [{"interval_seconds": "0"}, {"items": "[[15,-1,100]]"}, {"version": "2"}]
)
async def test_corrupt_policy_never_creates_units(redis_client, corrupt):
    """Los datos inválidos se rechazan antes de escribir cantidades o cortes."""
    redis = redis_client.redis
    await seed_merchant(redis, 7, (StockEntry(15, 1000, 100),), now=10000)
    await redis.hset(catalog_key(7), mapping=corrupt)
    stock = await redis.hgetall(RedisKeys.merchant_inventory(7))
    with pytest.raises(ValueError, match="persistida inválida"):
        await restock_merchant(redis, 7, now=13600)
    assert await redis.hgetall(RedisKeys.merchant_inventory(7)) == stock
    assert await redis.hget(catalog_key(7), "last_restock") == "10000"


@pytest.mark.asyncio
async def test_existing_stock_does_not_depend_on_new_toml_seed(redis_client):
    """Una semilla cambiada o inválida no sustituye la política Redis existente."""
    redis = redis_client.redis
    await seed_merchant(redis, 7, (StockEntry(15, 1000, 100),), now=10000)
    await redis.hset(RedisKeys.merchant_inventory(7), "slot_1", "15:5")
    await seed_merchant(redis, 7, (StockEntry(15, 1000000, 1000000),))
    assert await redis.hget(RedisKeys.merchant_inventory(7), "slot_1") == "15:5"
    with pytest.raises(ValueError, match="fuera de rango"):
        await seed_merchant(redis, 7, (StockEntry(15, 1000000, 1000000),), replace_catalog=True)


@pytest.mark.asyncio
async def test_invalid_merchant_does_not_starve_other_restocks(redis_client):
    """El worker aísla una política corrupta y sigue atendiendo los otros NPC."""
    redis = redis_client.redis
    for npc_id in (7, 8):
        await seed_merchant(redis, npc_id, (StockEntry(15, 1000, 100),), now=10000)
        await redis.hset(RedisKeys.merchant_inventory(npc_id), "slot_1", "15:1")
    await redis.hset(catalog_key(7), "interval_seconds", "0")
    await EconomyMaintenance(redis)._sweep("merchant:*:catalog", restock_merchant)
    assert await redis.hget(RedisKeys.merchant_inventory(7), "slot_1") == "15:1"
    assert await redis.hget(RedisKeys.merchant_inventory(8), "slot_1") == "15:1000"
