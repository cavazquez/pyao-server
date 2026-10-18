"""Credencial Redis por archivo, sin defaults secretos ni sobreescritura."""

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.config.game_config import RedisConfig
from src.operations.redis_secret import create_secret
from src.utils.redis_client import RedisClient


def test_generated_secret_is_private_and_never_overwritten(tmp_path):
    """Generar otra vez falla antes de truncar una credencial vigente."""
    path = tmp_path / "private/redis-password"
    create_secret(path)
    original = path.read_bytes()
    assert path.stat().st_mode & 0o777 == 0o600
    assert len(original) >= 40
    with pytest.raises(FileExistsError):
        create_secret(path)
    assert path.read_bytes() == original


@pytest.mark.asyncio
async def test_password_file_reaches_constructor_without_logging(tmp_path, monkeypatch, caplog):
    """El constructor recibe el canario y el modelo/log sólo conservan la ruta."""
    caplog.set_level(logging.DEBUG)
    path = tmp_path / "redis-password"
    canary = "SyntheticRedisSecret106"
    path.write_text(canary + "\n")
    settings = RedisConfig(password_file=path)
    assert canary not in repr(settings)
    monkeypatch.setattr(RedisClient, "_instance", None)
    monkeypatch.setattr(RedisClient, "_redis", None)
    raw = MagicMock()
    raw.ping = AsyncMock(return_value=True)
    raw.exists = AsyncMock(return_value=True)
    raw.set = AsyncMock(return_value=False)
    raw.aclose = AsyncMock()
    client = RedisClient()
    with (
        patch("src.utils.redis_client.redis.BlockingConnectionPool") as constructor,
        patch("src.utils.redis_client.redis.Redis.from_pool", return_value=raw),
    ):
        await client.connect(settings)
        assert constructor.call_args.kwargs["password"] == canary
    await client.disconnect()
    assert canary not in caplog.text
    assert canary.encode().hex() not in caplog.text


@pytest.mark.parametrize("value", ["", "first\nsecond"])
def test_invalid_secret_is_rejected_without_its_content(tmp_path, value):
    """La configuración nunca sustituye un secreto inválido por acceso anónimo."""
    path = tmp_path / "redis-password"
    path.write_text(value)
    with pytest.raises(ValueError, match="una sola línea"):
        RedisConfig(password_file=path).read_password()
