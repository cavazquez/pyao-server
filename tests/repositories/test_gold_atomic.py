"""Concurrencia e idempotencia de saldos, incluso con ACK perdido."""

import asyncio
import time
from unittest.mock import patch

import pytest
from redis.exceptions import ConnectionError as RedisConnectionError

from src.models.item_constants import MAX_PLAYER_GOLD
from src.repositories.player_repository import PlayerRepository
from src.utils.gold_atomic import operation_id
from src.utils.redis_config import RedisKeys


@pytest.mark.asyncio
async def test_parallel_credits_and_competing_debits(redis_client):
    """Verifica conservación y rechazo sin cambios parciales."""
    repo = PlayerRepository(redis_client)
    await repo.update_gold(1, 0)
    await asyncio.gather(*(repo.add_gold(1, 1) for _ in range(100)))
    assert await repo.get_gold(1) == 100
    results = await asyncio.gather(repo.remove_gold(1, 80), repo.remove_gold(1, 80))
    assert sorted(results) == [False, True]
    assert await repo.get_gold(1) == 20


@pytest.mark.asyncio
async def test_limits_and_capped_credit(redis_client):
    """Verifica conservación y rechazo sin cambios parciales."""
    repo = PlayerRepository(redis_client)
    await repo.update_gold(1, MAX_PLAYER_GOLD - 2)
    with pytest.raises(ValueError, match="límite"):
        await repo.add_gold(1, 3)
    assert await repo.add_gold_capped(1, 9) == (2, MAX_PLAYER_GOLD)
    for invalid in [-1, MAX_PLAYER_GOLD + 1, True]:
        for method in [repo.add_gold, repo.remove_gold, repo.update_gold]:
            with pytest.raises(ValueError, match="rango"):
                await method(1, invalid)
    assert await repo.get_gold(1) == MAX_PLAYER_GOLD


@pytest.mark.asyncio
async def test_receipt_survives_lost_exec_ack(redis_client):
    """Verifica conservación y rechazo sin cambios parciales."""
    repo = PlayerRepository(redis_client)
    await repo.update_gold(1, 100)
    pipeline_type = type(redis_client.redis.pipeline())
    original = pipeline_type.execute
    failed_once = False

    async def lose_ack(self, *args: object, **kwargs: object):
        nonlocal failed_once
        result = await original(self, *args, **kwargs)
        if not failed_once:
            failed_once = True
            message = "simulated lost ACK after commit"
            raise RedisConnectionError(message)
        return result

    identity = operation_id()
    with patch.object(pipeline_type, "execute", lose_ack):
        assert await repo.remove_gold(1, 30, operation_id=identity)
    assert failed_once
    assert await repo.remove_gold(1, 30, operation_id=identity)
    assert await repo.get_gold(1) == 70
    with pytest.raises(ValueError, match="otra petición"):
        await repo.remove_gold(1, 31, operation_id=identity)
    assert await repo.get_gold(1) == 70


@pytest.mark.asyncio
async def test_expired_request_cannot_reapply_after_receipt_expiry(redis_client):
    """Verifica conservación y rechazo sin cambios parciales."""
    repo = PlayerRepository(redis_client)
    await repo.update_gold(1, 100)
    identity = operation_id()
    await repo.remove_gold(1, 20, operation_id=identity)
    await redis_client.redis.delete(f"operation:gold:{RedisKeys.player_user_stats(1)}:{identity}")
    with (
        patch("src.utils.gold_atomic.time.time", return_value=time.time() + 601),
        pytest.raises(ValueError, match="vencida"),
    ):
        await repo.remove_gold(1, 20, operation_id=identity)
    assert await repo.get_gold(1) == 80


@pytest.mark.asyncio
async def test_level_update_preserves_concurrent_gold(redis_client):
    """Verifica conservación y rechazo sin cambios parciales."""
    repo = PlayerRepository(redis_client)
    await repo.update_gold(1, 500)
    await repo.set_stats(1, 10, 10, 10, 10, 10, 10, 1, 2, 300, 100, preserve_gold=True)
    assert await repo.get_gold(1) == 500
