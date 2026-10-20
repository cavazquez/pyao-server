"""El arranque completa ausencias y conserva valores confirmados, incluso con dos loaders."""

import asyncio
import json
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from fakeredis.aioredis import FakeRedis

from src.core.data_initializer import DataInitializer
from src.core.redis_initializer import RedisInitializer
from src.core.schema_manager import CURRENT_SCHEMA_VERSION, SCHEMA_KEY, SchemaMigrationError
from src.models.crafting_data_loader import CRAFTING_KEY
from src.models.skill_data_loader import SKILL_RULES_KEY
from src.utils.redis_client import RedisClient


@pytest_asyncio.fixture
async def client(monkeypatch):
    """Ejecuta el bootstrap real; sólo el transporte se reemplaza.

    Yields:
        Wrapper con un Redis aislado para cada prueba.
    """
    monkeypatch.setattr(RedisClient, "_instance", None)
    wrapper = RedisClient()
    wrapper._redis = FakeRedis(decode_responses=True)
    monkeypatch.setattr(RedisClient, "connect", AsyncMock())
    try:
        yield wrapper
    finally:
        await wrapper.disconnect()


@pytest.mark.asyncio
async def test_empty_bootstrap_and_repeated_boot_preserve_custom_state(client):
    """Cuentas, IDs, oro, inventario y configuración no son semillas descartables."""
    await RedisInitializer.initialize()
    redis = client.redis
    assert await redis.hget(SCHEMA_KEY, "version") == str(CURRENT_SCHEMA_VERSION)
    assert len(json.loads(await redis.get(CRAFTING_KEY))) > 0
    assert json.loads(await redis.get(SKILL_RULES_KEY))["version"] == 1
    assert await redis.hget("world:home:6", "map") == "151"
    strings = {
        "server:motd": "Bienvenido a Argentum Online!\nServidor en desarrollo.",
        "server:dice:min_value": "0",
        "config:effects:hunger_thirst:enabled": "0",
        "config:server:host": "",
        "account:id:counter": "812",
        "config:crafting:recipes": "[]",
        "config:skills:rules": await redis.get(SKILL_RULES_KEY),
    }
    for key, value in strings.items():
        await redis.set(key, value)
    await redis.expire(SKILL_RULES_KEY, 3600)
    hashes = {
        "world:home:1": {"map": "34", "x": "0", "y": "99", "heading": "0"},
        "player:812:stats": {"gold": "0", "bank_gold": "42", "level": "35"},
        "player:812:inventory": {"slot_1": "15:2", "slot_2": ""},
        "player:812:equipment": {"weapon": "15"},
        "player:812:bank": {"slot_1": "38:3"},
        "merchant:7:inventory": {"slot_1": "", "slot_20": "139:3"},
    }
    for key, fields in hashes.items():
        await redis.hset(key, mapping=fields)
    stock = await redis.hgetall("merchant:7:inventory")
    policy = await redis.hgetall("merchant:7:catalog")
    for _ in range(2):
        await RedisInitializer.initialize()
    for key, value in strings.items():
        assert await redis.get(key) == value, key
    for key, fields in hashes.items():
        for field, value in fields.items():
            assert await redis.hget(key, field) == value, (key, field)
    assert await redis.hgetall("merchant:7:inventory") == stock
    assert await redis.hgetall("merchant:7:catalog") == policy
    assert 3590 <= await redis.ttl(SKILL_RULES_KEY) <= 3600


@pytest.mark.asyncio
async def test_partial_bootstrap_completes_fields_without_falsey_replacement(client):
    """Un hash incompleto no omite otras ciudades ni convierte cero en default."""
    await RedisInitializer.initialize()
    redis = client.redis
    await redis.delete(CRAFTING_KEY, "world:home:2", "server:dice:max_value")
    await redis.hdel("world:home:1", "map", "heading")
    await redis.hset("world:home:1", mapping={"x": "0", "y": ""})
    await RedisInitializer.initialize()
    assert await redis.hgetall("world:home:1") == {"map": "1", "heading": "3", "x": "0", "y": ""}
    assert await redis.hget("world:home:2", "map") == "34"
    assert await redis.get("server:dice:max_value") == "18"
    assert json.loads(await redis.get(CRAFTING_KEY))


@pytest.mark.asyncio
async def test_concurrent_loaders_preserve_committed_updates(client):
    """SET NX y HSETNX no tienen una ventana lectura/escritura que pierda cambios."""
    redis = client.redis
    await redis.set(CRAFTING_KEY, "[]")
    await redis.hset("world:home:1", mapping={"x": "0", "map": "34"})
    await asyncio.gather(*(DataInitializer(client).initialize_all() for _ in range(2)))
    assert await redis.get(CRAFTING_KEY) == "[]"
    assert await redis.hget("world:home:1", "map") == "34"
    assert await redis.hget("world:home:1", "x") == "0"
    assert await redis.hget("world:home:1", "heading") == "3"


@pytest.mark.asyncio
@pytest.mark.parametrize("version", ["0", "4", "5", str(CURRENT_SCHEMA_VERSION + 1), "corrupto"])
async def test_incompatible_schema_is_rejected_before_any_seed(client, version):
    """Ni siquiera defaults o metadatos se escriben ante un esquema incompatible."""
    redis = client.redis
    await redis.hset(SCHEMA_KEY, "version", version)
    await redis.set("player:1:sentinel", "original", ex=3600)
    keys = sorted(await redis.keys("*"))
    with pytest.raises(SchemaMigrationError):
        await RedisInitializer.initialize()
    assert sorted(await redis.keys("*")) == keys
    assert await redis.hget(SCHEMA_KEY, "version") == version
    assert await redis.get("player:1:sentinel") == "original"
    assert 3590 <= await redis.ttl("player:1:sentinel") <= 3600
