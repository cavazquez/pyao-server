"""Guía opcional y diagnóstico sin cambios ni exposición de secretos Redis."""

import json
from unittest.mock import AsyncMock, Mock, patch

import pytest
from redis.exceptions import AuthenticationError
from redis.exceptions import ConnectionError as RedisConnectionError

from src.config.game_config import RedisConfig
from src.operations.redis_setup import check, guide


@pytest.mark.parametrize("host", ["localhost", "127.0.0.1", "redis.private.invalid"])
def test_guide_is_optional_safe_and_uses_configured_endpoint(host, tmp_path):
    """La guía no lee secretos; las URLs y las instrucciones pertenecen al operador."""
    config = RedisConfig(host=host, port=16379, db=4, password_file=tmp_path / "missing")
    with patch.object(RedisConfig, "read_password", side_effect=AssertionError("No leer")):
        value = guide(config)
    assert host in value
    assert "16379" in value
    assert "base 4" in value
    assert "sudo snap install redisinsight --channel=latest/stable" in value
    assert "--askpass" in value
    assert "appendonly=yes" in value
    assert "El cliente Godot no necesita" in value
    assert "https://snapcraft.io/redisinsight" in value


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("version", "aof", "fsync", "ok"),
    [
        ("8.10.2", "yes", "everysec", True),
        ("7.2.0", "yes", "always", True),
        ("7.0.0", "yes", "everysec", False),
        ("8.10.2", "no", "everysec", False),
        ("8.10.2", "yes", "no", False),
    ],
)
async def test_check_reads_only_ping_info_config_and_closes(version, aof, fsync, ok):
    """No WAITAOF, SET, semillas, instalación ni modificación de servicios."""
    client = Mock(spec=["ping", "info", "config_get", "aclose"])
    client.ping = AsyncMock(return_value=True)
    client.info = AsyncMock(return_value={"redis_version": version})
    client.config_get = AsyncMock(return_value={"appendonly": aof, "appendfsync": fsync})
    client.aclose = AsyncMock()
    with patch("src.operations.redis_setup.Redis", return_value=client):
        result = await check(RedisConfig(host="remote.private.invalid"))
    assert result["ok"] is ok
    assert result["mode"] == "remote"
    assert result["read_only"] is True
    assert result["insight_required"] is False
    client.info.assert_awaited_once_with("server")
    client.config_get.assert_awaited_once_with("appendonly", "appendfsync")
    client.aclose.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("error", [RedisConnectionError, AuthenticationError, TimeoutError])
async def test_connection_error_is_actionable_without_secrets(error, tmp_path):
    """Ni el archivo secreto ni el texto del error salen en el diagnóstico."""
    secret = "SYNTHETIC_SETUP_PASSWORD"
    path = tmp_path / "password"
    path.write_text(secret)
    client = Mock(spec=["ping", "aclose"])
    client.ping = AsyncMock(side_effect=error(secret))
    client.aclose = AsyncMock()
    with patch("src.operations.redis_setup.Redis", return_value=client):
        result = await check(RedisConfig(password_file=path))
    assert result["ok"] is False
    assert "--redis-guide" in result["message"]
    assert secret not in json.dumps(result)
    client.aclose.assert_awaited_once()
