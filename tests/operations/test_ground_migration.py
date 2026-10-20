"""El cambio de tipo del suelo se confirma junto al esquema y conserva cada stack."""

import json
from unittest.mock import Mock, patch

import pytest
from fakeredis import FakeRedis
from redis.exceptions import ConnectionError as RedisConnectionError

from src.core.schema_manager import MIGRATION_LOCK_KEY, SCHEMA_KEY, SchemaMigrationError
from src.operations.ground_migration import (
    active_ground_fingerprint,
    ground_fingerprint,
    ground_rewrites,
)
from src.operations.redis_schema import apply_ordered_steps
from src.utils.ground_state import GroundState, stack_identity
from src.utils.ground_storage import decode_fields
from src.utils.redis_config import RedisKeys


@pytest.mark.parametrize("decode", [True, False])
def test_backup_fingerprint_includes_expiring_ground_and_all_databases(decode):
    """El backup compara también suelo con TTL; no mezcla ni deja seleccionado otro DB."""
    with FakeRedis(decode_responses=decode) as client:
        client.info = Mock(return_value={"db0": {"keys": 1}, "db2": {"keys": 1}})
        key = RedisKeys.ground_items(1)
        client.set(key, '{"1,1":[]}', px=500000)
        client.select(2)
        client.hset(key, "1,1", "[]")
        client.pexpire(key, 600000)
        client.select(0)
        first = ground_fingerprint(client)
        assert set(first) == {"0", "2"}
        assert first["0"][key]["sha256"] != first["2"][key]["sha256"]
        assert client.type(key) in {"string", b"string"}
        client.set(key, '{"1,1":[{"item_id":1,"quantity":1}]}', keepttl=True)
        second = ground_fingerprint(client)
        assert second["0"][key]["sha256"] != first["0"][key]["sha256"]
        assert second["0"][key]["expires_at"] == first["0"][key]["expires_at"]
        assert second["2"] == first["2"]
        assert not active_ground_fingerprint({"0": {key: {"expires_at": 1, "sha256": "expired"}}})


def legacy(client, map_id=1, *, expiry=True):
    """Prepara IDs legados y metadatos que no se pueden perder.

    Returns:
        Estado esperado y vencimiento absoluto.
    """
    raw = json.dumps(
        {
            "1,1": [
                {"item_id": 1, "quantity": 2, "grh_index": 3, "owner_id": None, "custom": "keep"},
                {"item_id": 1, "quantity": 2},
            ],
            "100,100": [
                {
                    "item_id": 12,
                    "quantity": 1000,
                    "devaluation_day": 20000,
                    "devaluation_remainder": 9000,
                    "stack_id": stack_identity("existing"),
                }
            ],
        }
    )
    key = RedisKeys.ground_items(map_id)
    client.set(key, raw)
    if expiry:
        client.pexpire(key, 500000)
    return GroundState(map_id, raw), client.pexpiretime(key)


def setup(client):
    """Reserva una migración explícita desde v5 sin cambiar saldos."""
    client.hset(SCHEMA_KEY, "version", "5")
    client.set(MIGRATION_LOCK_KEY, "owner", ex=300)
    client.hset("player:1:user_stats", mapping={"gold": "1234", "level": "8"})
    client.set("bank:1:gold", "987")


def test_migrate_preserves_items_metadata_expiry_and_persistent_maps():
    """Un EXEC reemplaza JSON por hash y conserva el reloj original, sin doble paso."""
    with FakeRedis(decode_responses=True) as client:
        setup(client)
        first, expiry = legacy(client)
        second, persistent = legacy(client, 2, expiry=False)
        assert apply_ordered_steps(client, "owner", "verified-backup") == ["ground-hash-per-tile"]
        for map_id, state, expected_expiry in ((1, first, expiry), (2, second, persistent)):
            key = RedisKeys.ground_items(map_id)
            assert client.type(key) == "hash"
            assert decode_fields(map_id, client.hgetall(key)).tiles == state.tiles
            assert client.pexpiretime(key) == expected_expiry
        assert client.hget("player:1:user_stats", "gold") == "1234"
        assert client.get("bank:1:gold") == "987"
        assert client.hget(SCHEMA_KEY, "version") == "6"
        journal = client.hget(SCHEMA_KEY, "migration:6")
        assert json.loads(journal)["ground_maps"] == 2
        assert apply_ordered_steps(client, "owner", "verified-backup") == []
        assert client.hget(SCHEMA_KEY, "migration:6") == journal


@pytest.mark.parametrize(
    "raw",
    [
        "[]",
        "broken",
        '{"01,1":[{"item_id":1,"quantity":1}]}',
        json.dumps({"1,1": [{"item_id": 1, "quantity": 1}] * 11}),
    ],
)
def test_invalid_source_aborts_before_changing_any_map_or_schema(raw):
    """Un mapa inválido no deja otro convertido ni avanza el esquema."""
    with FakeRedis(decode_responses=True) as client:
        setup(client)
        expected, _ = legacy(client)
        original = client.get(RedisKeys.ground_items(1))
        client.set(RedisKeys.ground_items(2), raw)
        with pytest.raises(SchemaMigrationError, match="inválido"):
            apply_ordered_steps(client, "owner", "verified-backup")
        assert client.get(RedisKeys.ground_items(1)) == original
        assert GroundState(1, original).tiles == expected.tiles
        assert client.get(RedisKeys.ground_items(2)) == raw
        assert client.hget(SCHEMA_KEY, "version") == "5"


def test_lost_migration_ack_cannot_repeat_conversion_or_extend_expiry():
    """Una respuesta perdida después de EXEC se resuelve leyendo el esquema v6."""
    with FakeRedis(decode_responses=True) as client:
        setup(client)
        expected, expiry = legacy(client)
        pipeline_type = type(client.pipeline())
        execute = pipeline_type.execute

        def uncertain(pipe, *args: object, **kwargs: object):
            execute(pipe, *args, **kwargs)
            message = "ACK lost after schema commit"
            raise RedisConnectionError(message)

        with patch.object(pipeline_type, "execute", uncertain), pytest.raises(RedisConnectionError):
            apply_ordered_steps(client, "owner", "verified-backup")
        assert apply_ordered_steps(client, "owner", "verified-backup") == []
        assert decode_fields(1, client.hgetall(RedisKeys.ground_items(1))).tiles == expected.tiles
        assert client.pexpiretime(RedisKeys.ground_items(1)) == expiry


def test_changed_source_is_revalidated_before_type_replacement():
    """La segunda lectura detecta una escritura entre el plan y su WATCH."""
    with FakeRedis(decode_responses=True) as client:
        setup(client)
        legacy(client)
        original = ground_rewrites
        calls = 0

        def changed(redis):
            nonlocal calls
            result = original(redis)
            calls += 1
            if calls == 1:
                data = json.loads(redis.get(RedisKeys.ground_items(1)))
                data["1,1"][0]["quantity"] = 7
                redis.set(RedisKeys.ground_items(1), json.dumps(data))
            return result

        with patch("src.operations.redis_schema.ground_rewrites", changed):
            apply_ordered_steps(client, "owner", "verified-backup")
        assert calls >= 3
        assert (
            decode_fields(1, client.hgetall(RedisKeys.ground_items(1))).tile(1, 1)[0]["quantity"]
            == 7
        )
