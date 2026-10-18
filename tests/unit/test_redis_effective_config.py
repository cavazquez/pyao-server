"""Conexión Redis con configuración central, sin servicios externos."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fakeredis.aioredis import FakeAsyncRedisConnection, FakeRedis
from redis.asyncio import BlockingConnectionPool
from redis.exceptions import ConnectionError as RedisConnectionError

from src.config.config_manager import ConfigManager
from src.config.game_config import GameConfig
from src.core.redis_initializer import RedisInitializer
from src.utils.redis_client import RedisClient
from src.utils.redis_config import RedisConfig


@pytest.mark.asyncio
@pytest.mark.parametrize("override", [False, True])
async def test_file_and_environment_reach_redis_constructor(tmp_path, monkeypatch, override):
    """El endpoint, pool y timeouts efectivos llegan al constructor de redis-py."""
    path = tmp_path / "server.toml"
    path.write_text(
        '[redis]\nhost="cache-file"\nport=6381\ndb=3\nmax_connections=7\n'
        "socket_timeout=2.5\nsocket_connect_timeout=1.25\npool_timeout=3.5\n"
    )
    if override:
        monkeypatch.setenv("PYAO_REDIS__HOST", "cache-env")
        monkeypatch.setenv("PYAO_REDIS__PORT", "6382")
        monkeypatch.setenv("PYAO_REDIS__DB", "4")
        monkeypatch.setenv("PYAO_REDIS__MAX_CONNECTIONS", "9")
        monkeypatch.setenv("PYAO_REDIS__POOL_TIMEOUT", "4.5")
    effective = GameConfig.from_toml(path).redis
    monkeypatch.setattr(RedisClient, "_instance", None)
    monkeypatch.setattr(RedisClient, "_redis", None)
    client = RedisClient()
    raw = MagicMock()
    raw.ping = AsyncMock(return_value=True)
    raw.exists = AsyncMock(return_value=True)
    raw.set = AsyncMock(return_value=False)
    raw.aclose = AsyncMock()
    with (
        patch("src.utils.redis_client.redis.BlockingConnectionPool") as constructor,
        patch("src.utils.redis_client.redis.Redis.from_pool", return_value=raw) as client_factory,
    ):
        await client.connect(effective)
        constructor.assert_called_once_with(
            host="cache-env" if override else "cache-file",
            password=None,
            port=6382 if override else 6381,
            db=4 if override else 3,
            max_connections=9 if override else 7,
            timeout=4.5 if override else 3.5,
            decode_responses=True,
            socket_timeout=2.5,
            socket_connect_timeout=1.25,
        )
        client_factory.assert_called_once_with(constructor.return_value)
    await client.disconnect()


@pytest.mark.asyncio
async def test_initializer_injects_central_settings():
    """El arranque nunca llama connect con defaults independientes."""
    client = MagicMock()
    client.connect = AsyncMock()
    client.initialize_defaults = AsyncMock()
    client.redis = FakeRedis(decode_responses=True)
    repo = MagicMock()
    repo.reset_connections_count = AsyncMock()
    repo.set_uptime_start = AsyncMock()
    settings = RedisConfig(host="redis-private", port=6390, db=8, max_connections=11)
    with (
        patch(
            "src.core.redis_initializer.config_manager.get_section",
            return_value=settings.model_dump(),
        ),
        patch("src.core.redis_initializer.RedisClient", return_value=client),
        patch("src.core.redis_initializer.DataInitializer") as data,
        patch("src.core.redis_initializer.ServerRepository", return_value=repo),
        patch.object(RedisInitializer, "_initialize_dice_config", AsyncMock()),
        patch.object(RedisInitializer, "_initialize_motd", AsyncMock()),
        patch.object(RedisInitializer, "_initialize_effects_config", AsyncMock()),
    ):
        data.return_value.initialize_all = AsyncMock()
        assert await RedisInitializer.initialize() is client
    client.connect.assert_awaited_once_with(settings, seed_defaults=False)
    await client.redis.aclose()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("port", 0),
        ("db", -1),
        ("max_connections", 0),
        ("pool_timeout", 0),
        ("socket_timeout", 0),
        ("socket_connect_timeout", -1),
    ],
)
def test_invalid_configuration_never_falls_back(tmp_path, monkeypatch, field, value):
    """Un archivo inválido aborta, y corregirlo permite un nuevo intento."""
    path = tmp_path / "server.toml"
    path.write_text(f'[redis]\nhost="private-cache"\n{field}={value}\n')
    monkeypatch.setattr(ConfigManager, "_instance", None)
    monkeypatch.setattr(ConfigManager, "_initialized", False, raising=False)
    monkeypatch.setattr(ConfigManager, "_config_file", path, raising=False)
    with pytest.raises(ValueError, match="Error validando configuración"):
        ConfigManager()
    path.write_text('[redis]\nhost="private-cache"\n')
    assert ConfigManager().get("redis.host") == "private-cache"


@pytest.mark.asyncio
@pytest.mark.parametrize("outcome", ["release", "timeout", "cancel"])
async def test_saturated_pool_waits_with_deadline_and_releases_on_cancel(monkeypatch, outcome):
    """Un pico espera sin bloquear el loop; timeout/cancelación no consumen conexiones."""
    monkeypatch.setattr(RedisClient, "_instance", None)
    monkeypatch.setattr(RedisClient, "_redis", None)
    pool = BlockingConnectionPool(
        max_connections=1,
        timeout=0.1,
        connection_class=FakeAsyncRedisConnection,
        decode_responses=True,
    )
    client = RedisClient()
    with patch("src.utils.redis_client.redis.BlockingConnectionPool", return_value=pool):
        await client.connect(RedisConfig(max_connections=1), seed_defaults=False)
    held = await pool.get_connection()
    try:
        pending = asyncio.create_task(client.set("pool:probe", "saved"))
        await asyncio.sleep(0.01)
        assert not pending.done()
        assert len(pool._in_use_connections) == 1
        if outcome == "release":
            await pool.release(held)
            held = None
            assert await pending
        elif outcome == "timeout":
            with pytest.raises(RedisConnectionError, match="No connection available"):
                await pending
        else:
            pending.cancel()
            with pytest.raises(asyncio.CancelledError):
                await pending
        if held is not None:
            await pool.release(held)
            held = None
        assert await client.set("pool:probe", "saved")
        assert await client.get("pool:probe") == "saved"
        assert not pool._in_use_connections
    finally:
        if held is not None:
            await pool.release(held)
        await client.disconnect()
    assert all(not connection.is_connected for connection in pool._available_connections)
