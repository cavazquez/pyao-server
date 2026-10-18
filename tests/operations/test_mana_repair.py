"""Reparación de datos históricos de maná con versión y auditoría atómicas."""

from fakeredis import FakeRedis

from src.core.schema_manager import CURRENT_SCHEMA_VERSION, MIGRATION_LOCK_KEY, SCHEMA_KEY
from src.operations.mana_repair import mana_repairs
from src.operations.redis_schema import apply_ordered_steps


def test_mana_migration_preserves_other_progress_and_is_idempotent() -> None:
    """Repara sólo maná y registra originales sin cambiar oro, items o experiencia."""
    with FakeRedis(decode_responses=True) as raw:
        raw.set(MIGRATION_LOCK_KEY, "synthetic-owner", ex=60)
        raw.hset(
            "player:1:user_stats",
            mapping={
                "min_mana": "500000",
                "max_mana": "500000",
                "gold": "1234",
                "experience": "789",
            },
        )
        raw.hset("player:2:user_stats", mapping={"min_mana": "32767", "max_mana": "32767"})
        raw.hset("player:1:inventory", mapping={"slot_30": "1:2"})
        before = raw.hgetall("player:1:user_stats")
        assert list(mana_repairs(raw)) == ["player:1:user_stats"]
        assert raw.hgetall("player:1:user_stats") == before  # Audit no modifica.
        assert (
            apply_ordered_steps(raw, "synthetic-owner", "synthetic-backup")[-1]
            == "normalize-mana-int16"
        )
        values = raw.hgetall("player:1:user_stats")
        assert values["min_mana"] == values["max_mana"] == "32767"
        assert values["migration:mana:maximum_before"] == "500000"
        assert values["gold"] == "1234"
        assert values["experience"] == "789"
        assert raw.hget("player:1:inventory", "slot_30") == "1:2"
        assert raw.hget(SCHEMA_KEY, "version") == str(CURRENT_SCHEMA_VERSION)
        assert apply_ordered_steps(raw, "synthetic-owner", "synthetic-backup") == []
        assert mana_repairs(raw) == {}


def test_new_affected_key_is_watched_before_any_repair() -> None:
    """Un segundo personaje descubierto al revalidar obliga a reservar todo de nuevo."""
    from unittest.mock import patch  # noqa: PLC0415

    with FakeRedis(decode_responses=True) as raw:
        raw.set(MIGRATION_LOCK_KEY, "synthetic-owner", ex=60)
        raw.hset("player:1:user_stats", mapping={"min_mana": "40000", "max_mana": "40000"})
        reads = 0

        def changing_plan(client):
            nonlocal reads
            reads += 1
            if reads == 2:
                raw.hset("player:2:user_stats", mapping={"min_mana": "50000", "max_mana": "50000"})
            return mana_repairs(client)

        with patch("src.operations.redis_schema.mana_repairs", side_effect=changing_plan):
            apply_ordered_steps(raw, "synthetic-owner", "synthetic-backup")
        assert reads >= 4
        assert raw.hget("player:1:user_stats", "max_mana") == "32767"
        assert raw.hget("player:2:user_stats", "max_mana") == "32767"
