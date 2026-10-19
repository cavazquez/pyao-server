"""Progreso clásico sobre Redis: presupuesto, topes, hambre y reintentos reales."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio

from src.models.skill_data_loader import SkillDataLoader
from src.models.skills import CATALOG, skill_migration_fields, skill_progress, skill_threshold
from src.repositories.player_repository import PlayerRepository
from src.services.player_progression import advance_player_level
from src.services.skill_allocation import allocate_skill_points
from src.services.skill_training import train_skill
from src.utils.gold_atomic import operation_id
from src.utils.redis_config import RedisKeys


@pytest_asyncio.fixture
async def progress_world(redis_client):
    """Jugador con asignación inicial completa y reglas reales cargadas desde TOML.

    Returns:
        Repositorio y conexión descartables.
    """
    await SkillDataLoader(redis_client).load()
    player = PlayerRepository(redis_client)
    await redis_client.hset(
        RedisKeys.player_user_stats(1),
        mapping={
            "level": "1",
            "experience": "0",
            "max_hp": "100",
            "min_hp": "50",
            "max_mana": "100",
            "min_mana": "50",
            "max_sta": "100",
            "min_sta": "100",
        },
    )
    await redis_client.hset(
        RedisKeys.player_stats(1), mapping={"constitution": "10", "intelligence": "10"}
    )
    await redis_client.hset(
        RedisKeys.player_hunger_thirst(1), mapping={"min_hunger": "100", "min_water": "100"}
    )
    await redis_client.hset(
        RedisKeys.player_skills(1),
        mapping={
            "progress_version": "2",
            "natural_xp_base": "200",
            "points": "0",
            "assigned_points": "10",
            "points_granted_through": "1",
            "level:talar": "0",
            "xp:talar": "0",
            "partial:talar": "0",
        },
    )
    return SimpleNamespace(player=player, redis=redis_client)


@pytest.mark.asyncio
async def test_skill_improvement_character_level_and_points_are_one_commit(progress_world):
    """Mejora, XP general y presupuesto se confirman en el mismo EXEC."""
    world = progress_world
    await world.redis.hset(RedisKeys.player_user_stats(1), "experience", "299")
    await world.redis.hset(RedisKeys.player_skills(1), "partial:talar", "150")
    identity = operation_id()
    first = await train_skill(world.player, 1, "talar", successful=True, identity=identity)
    saved = await world.redis.hgetall(RedisKeys.player_skills(1))
    stats = await world.redis.hgetall(RedisKeys.player_user_stats(1))
    assert first["skills_improved"] == ["talar"]
    assert saved["level:talar"] == "1"
    assert saved["partial:talar"] == "0"
    assert saved["xp:talar"] == "50"
    assert saved["points"] == "10"
    assert saved["points_granted_through"] == "2"
    assert stats["level"] == "2"
    assert stats["experience"] == "349"
    assert stats["max_hp"] == "200"
    assert stats["min_hp"] == "100"
    assert await train_skill(world.player, 1, "talar", successful=True, identity=identity) == first
    assert await world.redis.hgetall(RedisKeys.player_skills(1)) == saved
    assert await world.redis.hgetall(RedisKeys.player_user_stats(1)) == stats


@pytest.mark.asyncio
async def test_failure_has_twenty_xp_and_percentage(progress_world):
    """Verifica failure has twenty xp and percentage con Redis descartable."""
    world = progress_world
    await train_skill(world.player, 1, "talar", successful=False)
    saved = await world.redis.hgetall(RedisKeys.player_skills(1))
    progress = next(p for p in skill_progress(saved) if p.definition.key == "talar")
    assert progress.level == 0
    assert progress.experience == 20
    assert progress.percentage == 10
    assert (await world.redis.hgetall(RedisKeys.player_user_stats(1)))["experience"] == "0"


@pytest.mark.asyncio
@pytest.mark.parametrize("blocked", ["natural_cap", "hungry", "thirsty", "initial_assignment"])
async def test_ineligible_training_gives_no_xp(progress_world, blocked):
    """Verifica ineligible training gives no xp con Redis descartable."""
    world = progress_world
    if blocked == "natural_cap":
        await world.redis.hset(
            RedisKeys.player_skills(1), mapping={"level:talar": "3", "partial:talar": "199"}
        )
    elif blocked == "initial_assignment":
        await world.redis.hset(RedisKeys.player_skills(1), "assigned_points", "9")
    else:
        await world.redis.hset(
            RedisKeys.player_hunger_thirst(1),
            "min_hunger" if blocked == "hungry" else "min_water",
            "0",
        )
    before = await world.redis.hgetall(RedisKeys.player_skills(1))
    await train_skill(world.player, 1, "talar", successful=True)
    after = await world.redis.hgetall(RedisKeys.player_skills(1))
    assert after.get("xp:talar") == before.get("xp:talar")
    assert after.get("level:talar") == before.get("level:talar")


@pytest.mark.asyncio
@pytest.mark.parametrize("skill", ["liderazgo", "navegacion", "robustez", "agilidad"])
async def test_manual_skills_do_not_train(progress_world, skill):
    """Verifica manual skills do not train con Redis descartable."""
    world = progress_world
    await train_skill(world.player, 1, skill, successful=True)
    assert await world.redis.hget(RedisKeys.player_skills(1), f"xp:{skill}") is None


@pytest.mark.asyncio
async def test_parallel_level_checks_grant_points_once(progress_world):
    """Verifica parallel level checks grant points once con Redis descartable."""
    world = progress_world
    await world.redis.hset(RedisKeys.player_user_stats(1), "experience", "300")
    sender = AsyncMock()
    sender.connection.capabilities.enabled = 0
    results = await asyncio.gather(
        *(advance_player_level(world.player, 1, sender) for _ in range(4))
    )
    assert sum(r["points_gained"] for r in results) == 10
    assert await world.player.get_skill_points(1) == 10


@pytest.mark.asyncio
async def test_manual_allocation_retains_partial_and_total_xp(progress_world, monkeypatch):
    """Verifica manual allocation retains partial and total xp con Redis descartable."""
    world = progress_world
    monkeypatch.setattr("src.services.skill_allocation.require_durable", AsyncMock())
    await world.redis.hset(
        RedisKeys.player_skills(1),
        mapping={"points": "10", "partial:talar": "50", "xp:talar": "350"},
    )
    deltas = tuple((entry.skill_id, int(entry.key in {"robar", "talar"})) for entry in CATALOG)
    result = await allocate_skill_points(world.redis.redis, 1, operation_id(), deltas)
    assert result["applied"]
    saved = await world.redis.hgetall(RedisKeys.player_skills(1))
    assert saved["level:robar"] == "1"
    assert saved["level:talar"] == "1"
    assert saved["partial:talar"] == "50"
    assert saved["xp:talar"] == "350"
    assert saved["points"] == "8"


def test_migration_retains_history_and_own_skills():
    """Verifica migration retains history and own skills con Redis descartable."""
    old = {
        "progress_version": "1",
        "xp_per_level": "100",
        "level:talar": "7",
        "xp:talar": "150",
        "robustez": "35",
        "agilidad": "20",
        "points": "0",
    }
    additions = skill_migration_fields(old)
    saved = old | additions
    assert saved["level:talar"] == "7"
    assert saved["xp:talar"] == "150"
    assert saved["partial:talar"] == str(skill_threshold(7) // 2)
    assert saved["robustez"] == "35"
    assert saved["level:robustez"] == "35"
    assert saved["agilidad"] == "20"
    assert saved["level:agilidad"] == "20"
    assert additions["assigned_points"] == "10"
    assert skill_migration_fields(saved) == {}
