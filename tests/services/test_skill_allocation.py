"""Presupuesto, concurrencia, reintentos y semántica separada de XP."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from redis.exceptions import ConnectionError as RedisConnectionError

from src.models.skills import CATALOG, skill_progress
from src.repositories.player_repository import PlayerRepository
from src.services.skill_allocation import allocate_skill_points
from src.utils.gold_atomic import operation_id
from src.utils.redis_config import RedisKeys


def deltas(skill_id=1, amount=5):
    """Construye los 22 pares canónicos, incluidos ceros para habilidades pendientes."""
    return tuple((entry.skill_id, amount if entry.skill_id == skill_id else 0) for entry in CATALOG)


@pytest.mark.asyncio
async def test_two_concurrent_requests_cannot_overspend_and_replay_is_once(redis_client):
    """Dos gastos de cinco compiten por ocho puntos, sin estados parciales."""
    key = RedisKeys.player_skills(1)
    await redis_client.hset(key, mapping={"points": "8", "level:magia": "10", "xp:magia": "77"})
    identities = [operation_id(), operation_id()]
    with patch("src.services.skill_allocation.require_durable", new=AsyncMock()):
        results = await asyncio.gather(
            *(
                allocate_skill_points(redis_client.redis, 1, identity, deltas())
                for identity in identities
            )
        )
        assert sum(result["applied"] for result in results) == 1
        winner = identities[
            next(index for index, result in enumerate(results) if result["applied"])
        ]
        assert (await allocate_skill_points(redis_client.redis, 1, winner, deltas()))["applied"]
    saved = await redis_client.hgetall(key)
    assert saved["points"] == "3"
    assert saved["level:magia"] == "15"
    assert saved["xp:magia"] == "77"
    assert (await PlayerRepository(redis_client).get_skills(1))["magia"] == 15


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "changes",
    [deltas(amount=-1), deltas(amount=9), deltas(23, 1), deltas(amount=100), deltas(amount=5)],
)
async def test_invalid_budget_delta_pending_skill_or_overflow_has_no_partial_write(
    redis_client, changes
):
    """Un delta inválido no destruye otros deltas válidos ni el presupuesto."""
    key = RedisKeys.player_skills(1)
    before = {"points": "8", "level:magia": "99", "xp:magia": "77"}
    await redis_client.hset(key, mapping=before)
    with patch("src.services.skill_allocation.require_durable", new=AsyncMock()):
        assert not (await allocate_skill_points(redis_client.redis, 1, operation_id(), changes))[
            "applied"
        ]
    assert await redis_client.hgetall(key) == before


@pytest.mark.asyncio
async def test_wrong_ids_and_changed_request_identity_are_rejected(redis_client):
    """Un ID no puede usarse para otra cuenta, otro delta o una lista reordenada."""
    await redis_client.hset(RedisKeys.player_skills(1), mapping={"points": "8"})
    identity = operation_id()
    with patch("src.services.skill_allocation.require_durable", new=AsyncMock()):
        with pytest.raises(ValueError, match="IDs"):
            await allocate_skill_points(redis_client.redis, 1, identity, deltas()[::-1])
        await allocate_skill_points(redis_client.redis, 1, identity, deltas())
        with pytest.raises(ValueError, match="reutilizado"):
            await allocate_skill_points(redis_client.redis, 1, identity, deltas(amount=1))


@pytest.mark.asyncio
async def test_allocated_level_and_later_experience_remain_independent(redis_client):
    """La siguiente ganancia de XP no borra niveles comprados con puntos."""
    key = RedisKeys.player_skills(1)
    await redis_client.hset(
        key, mapping={"points": "8", "level:talar": "10", "xp:talar": "90", "xp_per_level": "100"}
    )
    with patch("src.services.skill_allocation.require_durable", new=AsyncMock()):
        assert (await allocate_skill_points(redis_client.redis, 1, operation_id(), deltas(9, 5)))[
            "applied"
        ]
    await PlayerRepository(redis_client).add_skill_experience(1, "talar", 20)
    progress = next(
        entry
        for entry in skill_progress(await redis_client.hgetall(key))
        if entry.definition.skill_id == 9
    )
    assert progress.level == 16
    assert progress.experience == 110
    assert progress.percentage == 10


@pytest.mark.asyncio
@pytest.mark.parametrize("after_exec", [False, True])
async def test_lost_exec_ack_recovers_without_double_spending(redis_client, after_exec):
    """Un fallo antes o después de EXEC resuelve el mismo ID una sola vez."""
    key = RedisKeys.player_skills(1)
    await redis_client.hset(key, mapping={"points": "8", "level:magia": "10"})
    original = type(redis_client.redis.pipeline()).execute
    failed = False

    async def fail_once(self, *args: object, **kwargs: object):
        nonlocal failed
        if not failed:
            failed = True
            if after_exec:
                await original(self, *args, **kwargs)
            message = "ACK de prueba perdido"
            raise RedisConnectionError(message)
        return await original(self, *args, **kwargs)

    identity = operation_id()
    with (
        patch("src.services.skill_allocation.require_durable", new=AsyncMock()),
        patch.object(type(redis_client.redis.pipeline()), "execute", fail_once),
    ):
        assert (await allocate_skill_points(redis_client.redis, 1, identity, deltas()))["applied"]
        assert (await allocate_skill_points(redis_client.redis, 1, identity, deltas()))["applied"]
    assert await redis_client.hgetall(key) == {
        "points": "3",
        "level:magia": "15",
        "assigned_points": "5",
    }
