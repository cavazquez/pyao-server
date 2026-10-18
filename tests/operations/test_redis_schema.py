"""Versiones, conservación y recuperación de una confirmación de migración perdida."""

from secrets import token_urlsafe
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fakeredis import FakeRedis
from fakeredis.aioredis import FakeRedis as AsyncFakeRedis
from redis.exceptions import ConnectionError as RedisConnectionError

from src.core.redis_initializer import RedisInitializer
from src.core.schema_manager import (
    CURRENT_SCHEMA_VERSION,
    MIGRATION_LOCK_KEY,
    SCHEMA_KEY,
    SchemaMigrationError,
    ensure_schema_ready,
)
from src.operations.redis_schema import apply_ordered_steps, release_lock


@pytest.mark.asyncio
async def test_new_database_initializes_but_legacy_and_future_fail_before_seeds():
    """Una base vieja o futura no se reinicializa al intentar arrancar."""
    raw = AsyncFakeRedis(decode_responses=True)
    try:
        await raw.set("config:server:port", "7666")
        await ensure_schema_ready(raw)
        assert await raw.hget(SCHEMA_KEY, "version") == str(CURRENT_SCHEMA_VERSION)
        await raw.delete(SCHEMA_KEY)
        await raw.hset("account:legacy:data", mapping={"user_id": "1"})
        with pytest.raises(SchemaMigrationError, match="legado"):
            await ensure_schema_ready(raw)
        assert await raw.hget("account:legacy:data", "user_id") == "1"
        await raw.hset(SCHEMA_KEY, "version", str(CURRENT_SCHEMA_VERSION + 1))
        with pytest.raises(SchemaMigrationError, match="incompatible"):
            await ensure_schema_ready(raw)
        assert await raw.hget("account:legacy:data", "user_id") == "1"
    finally:
        await raw.aclose()


@pytest.mark.asyncio
async def test_future_schema_does_not_load_defaults_or_game_data():
    """El arranque valida el esquema antes de escribir defaults y cargar seeds."""
    raw = AsyncFakeRedis(decode_responses=True)
    await raw.hset(SCHEMA_KEY, "version", str(CURRENT_SCHEMA_VERSION + 1))
    client = MagicMock()
    client.redis = raw
    client.connect = AsyncMock()
    client.initialize_defaults = AsyncMock()
    try:
        with (
            patch("src.core.redis_initializer.RedisClient", return_value=client),
            patch("src.core.redis_initializer.DataInitializer") as seeds,
            pytest.raises(SchemaMigrationError, match="incompatible"),
        ):
            await RedisInitializer.initialize()
        seeds.assert_not_called()
        client.initialize_defaults.assert_not_awaited()
        assert await raw.hget(SCHEMA_KEY, "version") == str(CURRENT_SCHEMA_VERSION + 1)
    finally:
        await raw.aclose()


def test_lost_ack_after_commit_is_recoverable_without_duplicate_step():
    """Si EXEC se aplicó pero se perdió la respuesta, repetir conserva versión/journal."""
    raw = FakeRedis(decode_responses=True)
    claim = token_urlsafe(16)
    raw.set(MIGRATION_LOCK_KEY, claim, ex=60)
    raw.hset("player:1:stats", mapping={"gold": "1234", "level": "7"})
    with raw.pipeline() as pipe:
        pipeline_type = type(pipe)
    execute = pipeline_type.execute
    already_failed = False

    def lose_ack(self, *args: object, **kwargs: object):
        nonlocal already_failed
        result = execute(self, *args, **kwargs)
        if not already_failed:
            already_failed = True
            msg = "Respuesta perdida después de EXEC"
            raise RedisConnectionError(msg)
        return result

    try:
        with patch.object(pipeline_type, "execute", lose_ack), pytest.raises(RedisConnectionError):
            apply_ordered_steps(raw, claim, "synthetic-backup-digest")
        assert apply_ordered_steps(raw, claim, "synthetic-backup-digest") == []
        assert raw.hget(SCHEMA_KEY, "version") == str(CURRENT_SCHEMA_VERSION)
        assert raw.hlen(SCHEMA_KEY) == 2
        assert raw.hget("player:1:stats", "gold") == "1234"
    finally:
        raw.close()


def test_releasing_an_expired_owner_does_not_remove_new_migration():
    """El propietario anterior no libera la reserva de otra migración."""
    raw = FakeRedis(decode_responses=True)
    old, new = token_urlsafe(16), token_urlsafe(16)
    try:
        raw.set(MIGRATION_LOCK_KEY, new, ex=60)
        release_lock(raw, old)
        assert raw.get(MIGRATION_LOCK_KEY) == new
        with pytest.raises(SchemaMigrationError, match="perdió su reserva"):
            apply_ordered_steps(raw, old, "synthetic-backup-digest")
        assert raw.hget(SCHEMA_KEY, "version") is None
    finally:
        raw.close()
