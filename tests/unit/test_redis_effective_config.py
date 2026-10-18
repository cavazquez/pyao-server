"""Conexión Redis con configuración central, sin servicios externos."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

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
        "socket_timeout=2.5\nsocket_connect_timeout=1.25\n"
    )
    if override:
        monkeypatch.setenv("PYAO_REDIS__HOST", "cache-env")
        monkeypatch.setenv("PYAO_REDIS__PORT", "6382")
        monkeypatch.setenv("PYAO_REDIS__DB", "4")
        monkeypatch.setenv("PYAO_REDIS__MAX_CONNECTIONS", "9")
    effective = GameConfig.from_toml(path).redis
    monkeypatch.setattr(RedisClient, "_instance", None)
    monkeypatch.setattr(RedisClient, "_redis", None)
    client = RedisClient()
    raw = MagicMock()
    raw.ping = AsyncMock(return_value=True)
    raw.exists = AsyncMock(return_value=True)
    raw.aclose = AsyncMock()
    with patch("src.utils.redis_client.redis.Redis", return_value=raw) as constructor:
        await client.connect(effective)
        constructor.assert_called_once_with(
            host="cache-env" if override else "cache-file",
            password=None,
            port=6382 if override else 6381,
            db=4 if override else 3,
            max_connections=9 if override else 7,
            decode_responses=True,
            socket_timeout=2.5,
            socket_connect_timeout=1.25,
        )
    await client.disconnect()


@pytest.mark.asyncio
async def test_initializer_injects_central_settings():
    """El arranque nunca llama connect con defaults independientes."""
    client = MagicMock()
    client.connect = AsyncMock()
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
    client.connect.assert_awaited_once_with(settings)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("port", 0),
        ("db", -1),
        ("max_connections", 0),
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
