"""Snapshots acotados para IA/broadcast, independientes de saldos y de otros frames."""

from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from src.repositories.player_repository import PlayerRepository
from src.utils.redis_config import RedisKeys

if TYPE_CHECKING:
    from src.utils.redis_client import RedisClient


@pytest.mark.asyncio
async def test_batches_preserve_position_defaults_and_health_semantics(
    redis_client: RedisClient,
) -> None:
    """Filtra muertos/ausentes, admite HP legacy y vuelve a leer cambios posteriores."""
    redis = redis_client.redis
    for user, stats in [
        (1, {"min_hp": "1"}),
        (2, {"hp": "0"}),
        (3, {"hp": "2"}),
        (4, {"level": "1"}),
    ]:
        await redis.hset(RedisKeys.player_position(user), mapping={"x": str(user)})
        await redis.hset(RedisKeys.player_user_stats(user), mapping=stats)
    await redis.hset(RedisKeys.player_position(5), mapping={"x": "5"})
    repo = PlayerRepository(redis_client)
    assert await repo.get_positions([]) == {}
    snapshot = await repo.get_positions([1, 2, 3, 4, 5, 6, 1], alive_only=True)
    assert list(snapshot) == [1, 3, 4]
    assert snapshot[1] == {"x": 1, "y": 50, "map": 1, "heading": 3}
    assert list(await repo.get_positions([1, 2, 3, 4, 5, 6])) == [1, 2, 3, 4, 5]
    await redis.hset(RedisKeys.player_user_stats(1), "min_hp", "0")
    await redis.hset(RedisKeys.player_position(3), "map", "2")
    assert await repo.get_positions([1, 3], alive_only=True) == {
        3: {"x": 3, "y": 50, "map": 2, "heading": 3}
    }
    assert snapshot[1]["map"] == 1


@pytest.mark.asyncio
async def test_large_position_read_uses_bounded_round_trips(redis_client: RedisClient) -> None:
    """600 IDs no construyen un pipeline sin límite y duplicados no añaden comandos."""
    redis = redis_client.redis
    with patch.object(redis, "pipeline", wraps=redis.pipeline) as pipeline:
        assert await PlayerRepository(redis_client).get_positions([*range(600), 1, 2]) == {}
    assert pipeline.call_count == 3
