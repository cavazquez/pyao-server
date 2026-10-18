"""Nivel/XP separados, progreso histórico preservado y crecimiento concurrente."""

import asyncio
import json
from pathlib import Path

import pytest
from fakeredis import FakeRedis

from src.core.schema_manager import MIGRATION_LOCK_KEY
from src.models.skills import CATALOG, skill_migration_fields, skill_progress
from src.network.msg_skills import build_skill_catalog_response
from src.operations.redis_schema import apply_ordered_steps
from src.repositories.player_repository import PlayerRepository
from src.utils.redis_config import RedisKeys

LEGACY = {
    "magia": "10",
    "robustez": "5",
    "agilidad": "3",
    "talar": "275",
    "pesca": "120",
    "mineria": "450",
    "carpinteria": "7",
    "herreria": "6",
    "supervivencia": "8",
    "liderazgo": "5",
}


def test_catalog_keeps_own_skills_and_explicit_unimplemented_ids() -> None:
    """No se pierde robustez/agilidad al representar los 20 IDs del cliente AO."""
    assert [entry.skill_id for entry in CATALOG] == list(range(1, 23))
    assert (CATALOG[20].key, CATALOG[21].key) == ("robustez", "agilidad")
    assert not CATALOG[1].implemented
    progress = {p.definition.key: p for p in skill_progress(LEGACY)}
    assert (progress["magia"].level, progress["magia"].experience) == (10, 0)
    assert (
        progress["talar"].level,
        progress["talar"].experience,
        progress["talar"].percentage,
    ) == (2, 275, 75)


def test_actual_builder_matches_shared_golden_catalog() -> None:
    """22 triples y presupuesto consumen exactamente 70 bytes."""
    fixtures = json.loads(
        (Path(__file__).parents[2] / "src/network/protocol/fixtures.json").read_text()
    )
    expected = next(bytes.fromhex(f["hex"]) for f in fixtures if f["name"] == "skills_catalog_v1")
    assert build_skill_catalog_response(skill_progress(LEGACY), 4) == expected
    assert len(expected) == 70


def test_migration_preserves_every_legacy_field_and_xp_idempotently() -> None:
    """La migración agrega campos, conserva progresión y no vuelve a convertir niveles."""
    with FakeRedis(decode_responses=True) as raw:
        raw.set(MIGRATION_LOCK_KEY, "synthetic-owner", ex=60)
        raw.hset("player:1:skills", mapping={**LEGACY, "points": "4", "unknown_legacy": "37"})
        apply_ordered_steps(raw, "synthetic-owner", "synthetic-backup")
        result = raw.hgetall("player:1:skills")
        assert all(result[key] == value for key, value in LEGACY.items())
        assert result["unknown_legacy"] == "37"
        assert result["points"] == "4"
        assert result["level:magia"] == "10"
        assert result["level:talar"] == "2"
        assert result["xp:talar"] == "275"
        assert skill_migration_fields(result) == {}
        assert apply_ordered_steps(raw, "synthetic-owner", "synthetic-backup") == []


@pytest.mark.asyncio
async def test_experience_updates_do_not_overwrite_levels_or_lose_concurrent_gains(
    redis_client,
) -> None:
    """Magia parte del nivel otorgado por clase y tala suma XP concurrente sin pérdidas."""
    repository = PlayerRepository(redis_client)
    await repository.set_skills(123, magia=10, talar=0)
    assert await repository.add_skill_experience(123, "magia", 100) == (100, True)
    assert (await repository.get_skills(123))["magia"] == 11
    await redis_client.hset(RedisKeys.player_skills(123), mapping={"xp:talar": "99"})
    results = await asyncio.gather(
        *(repository.add_skill_experience(123, "talar", 1) for _ in range(4))
    )
    progress = {p.definition.key: p for p in await repository.get_skill_progress(123)}
    assert progress["talar"].experience == 103
    assert progress["talar"].level == 1
    assert sum(leveled for _, leveled in results) == 1
    # Asignar un nivel explícito conserva la experiencia ya ganada.
    await repository.set_skills(123, magia=12)
    assert (await repository.get_skill_progress(123))[0].experience == 100
    with pytest.raises(ValueError, match="experiencia inválida"):
        await repository.add_skill_experience(123, "talar", -1)
    with pytest.raises(ValueError, match="nivel de habilidad inválida"):
        await repository.set_skills(123, magia=101)
