"""Suelo con Redis concreto: identidades, append concurrente y fallas visibles."""

import asyncio
import json
from unittest.mock import AsyncMock, patch

import pytest

from src.repositories.ground_items_repository import GroundItemsRepository
from src.utils.redis_config import RedisKeys


@pytest.fixture(autouse=True)
def durable_adapter():
    """Sustituye sólo fsync de Redis fake; el smoke nativo verifica la persistencia.

    Yields:
        Contexto de pruebas rápidas sin requerir comandos AOF de fakeredis.
    """
    with patch("src.repositories.ground_items_repository.require_durable", new=AsyncMock()):
        yield


@pytest.mark.asyncio
async def test_legacy_identity_is_stable_and_read_does_not_rewrite(redis_client):
    """Dos stacks legacy idénticos reciben identidades distintas sin modificar el JSON al leer."""
    repo = GroundItemsRepository(redis_client)
    raw = json.dumps([{"item_id": 1, "quantity": 2}, {"item_id": 1, "quantity": 2}])
    await redis_client.redis.hset(RedisKeys.ground_items(1), "50,50", raw)
    first = await repo.load_ground_items(1)
    second = await repo.load_ground_items(1)
    assert first == second
    assert first[50, 50][0]["stack_id"] != first[50, 50][1]["stack_id"]
    assert await redis_client.redis.hget(RedisKeys.ground_items(1), "50,50") == raw
    await repo.remove_ground_item(1, 50, 50, 0)
    remaining = (await repo.load_ground_items(1))[50, 50][0]
    assert remaining["stack_id"] == first[50, 50][1]["stack_id"]


@pytest.mark.asyncio
async def test_parallel_appends_and_identified_replay_preserve_all_stacks(redis_client):
    """El mapa compartido no pierde drops de productores que corren en paralelo."""
    repo = GroundItemsRepository(redis_client)
    results = await asyncio.gather(
        *(repo.add_ground_item(1, 50, 50, {"item_id": 1, "quantity": 1}) for _ in range(10))
    )
    assert all(result["applied"] for result in results)
    assert len((await repo.load_ground_items(1))[50, 50]) == 10
    assert not (await repo.add_ground_item(1, 50, 50, {"item_id": 1, "quantity": 1}))["applied"]
    assert 0 < await redis_client.redis.ttl(RedisKeys.ground_items(1)) <= 3600


@pytest.mark.asyncio
async def test_corruption_and_maintenance_guard_do_not_replace_data(redis_client):
    """Redis inválido no se trata como vacío; una sesión activa impide reemplazar snapshots."""
    repo = GroundItemsRepository(redis_client)
    await redis_client.redis.hset(RedisKeys.ground_items(1), "50,50", "corrupt")
    with pytest.raises(json.JSONDecodeError):
        await repo.load_ground_items(1)
    with pytest.raises(json.JSONDecodeError):
        await repo.add_ground_item(1, 50, 50, {"item_id": 1, "quantity": 1})
    assert await redis_client.redis.hget(RedisKeys.ground_items(1), "50,50") == "corrupt"
    await redis_client.set("session:1:owner", "nonce")
    with pytest.raises(RuntimeError, match="sin sesiones"):
        await repo.save_ground_items(1, {})
    assert await redis_client.redis.hget(RedisKeys.ground_items(1), "50,50") == "corrupt"
