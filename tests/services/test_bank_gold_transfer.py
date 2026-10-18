"""Concurrencia, límite e incertidumbre de transferencias conjuntas."""

import asyncio
from unittest.mock import patch

import pytest
from redis.exceptions import ConnectionError as RedisConnectionError

from src.models.item_constants import MAX_PLAYER_GOLD
from src.repositories.player_repository import PlayerRepository
from src.services.bank_gold_transfer import transfer_gold
from src.utils.gold_atomic import operation_id
from src.utils.redis_config import RedisKeys


@pytest.mark.asyncio
async def test_competing_transfers_preserve_total(redis_client):
    """Dos depósitos de ochenta compiten por cien; sólo uno se confirma."""
    repo = PlayerRepository(redis_client)
    await repo.update_gold(1, 100)
    results = await asyncio.gather(
        *(transfer_gold(redis_client.redis, 1, 80, "deposit", operation_id()) for _ in range(2))
    )
    assert sum(result["applied"] for result in results) == 1
    assert await repo.get_gold(1) == 20
    assert await redis_client.get(RedisKeys.bank_gold(1)) == "80"


@pytest.mark.asyncio
async def test_overflow_preserves_both_accounts(redis_client):
    """No se debita el banco cuando el jugador no puede recibir el total."""
    repo = PlayerRepository(redis_client)
    await repo.update_gold(1, MAX_PLAYER_GOLD)
    await redis_client.set(RedisKeys.bank_gold(1), "100")
    result = await transfer_gold(redis_client.redis, 1, 1, "withdraw", operation_id())
    assert not result["applied"]
    assert await repo.get_gold(1) == MAX_PLAYER_GOLD
    assert await redis_client.get(RedisKeys.bank_gold(1)) == "100"


@pytest.mark.asyncio
@pytest.mark.parametrize("after_commit", [False, True])
async def test_connection_failure_before_or_after_exec_never_splits_transfer(
    redis_client, after_commit
):
    """Caída antes de EXEC y ACK perdido después convergen al mismo commit único."""
    repo = PlayerRepository(redis_client)
    await repo.update_gold(1, 100)
    pipeline_type = type(redis_client.redis.pipeline())
    original = pipeline_type.execute
    failed_once = False

    async def faulty_execute(self, *args: object, **kwargs: object):
        nonlocal failed_once
        if failed_once:
            return await original(self, *args, **kwargs)
        failed_once = True
        if after_commit:
            await original(self, *args, **kwargs)
        message = "Falla simulada alrededor de EXEC"
        raise RedisConnectionError(message)

    identity = operation_id()
    with patch.object(pipeline_type, "execute", faulty_execute):
        result = await transfer_gold(redis_client.redis, 1, 40, "deposit", identity)
    assert result["applied"]
    assert await transfer_gold(redis_client.redis, 1, 40, "deposit", identity) == result
    assert await repo.get_gold(1) == 60
    assert await redis_client.get(RedisKeys.bank_gold(1)) == "40"
