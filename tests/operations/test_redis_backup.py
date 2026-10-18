"""Integridad y privacidad del backup sin requerir Docker en la suite rápida."""

from hashlib import sha256
from unittest.mock import Mock, patch

import pytest
from fakeredis import FakeRedis

from src.config.game_config import RedisConfig
from src.operations.redis_backup import (
    create_backup,
    persistent_snapshot,
    private_json,
    verify_backup,
)
from src.operations.redis_sandbox import RedisSandbox


def test_snapshot_is_canonical_across_all_databases():
    """Orden interno, bytes arbitrarios y claves temporales no cambian el digest."""
    first, second = FakeRedis(), FakeRedis()
    try:
        for client in [first, second]:
            # fakeredis no implementa INFO; los DBs y su contenido sí son reales.
            client.info = Mock(return_value={"db0": {"keys": 5}, "db2": {"keys": 1}})
            client.set("binary", b"\xff\x00")
            client.rpush("list", b"one", b"two")
            client.sadd("set", "b", "a")
            client.zadd("zset", {"a": 1.0, "b": 2.0})
        first.hset("hash", mapping={"a": "1", "b": "2"})
        second.hset("hash", mapping={"b": "2", "a": "1"})
        first.setex("session:volatile", 60, "temporary")
        for client in [first, second]:
            client.select(2)
            client.set("other-db", "preserved")
        snapshot = persistent_snapshot(first)
        assert snapshot == persistent_snapshot(second)
        assert snapshot["0"]["persistent_keys"] == 5
        assert snapshot["2"]["persistent_keys"] == 1
        assert "binary" not in repr(snapshot)
    finally:
        first.close()
        second.close()


def test_corruption_is_rejected_before_creating_a_destination(tmp_path):
    """Un archivo alterado no llega a iniciar un destino de restauración."""
    path = tmp_path / "backup.rdb"
    path.write_bytes(b"synthetic-rdb")
    private_json(
        path.with_suffix(".rdb.json"),
        {"format": 1, "sha256": sha256(path.read_bytes()).hexdigest(), "persistent_state": {}},
    )
    path.write_bytes(b"corrupted-rdb")
    with patch("src.operations.redis_backup.RedisSandbox") as destination:
        with pytest.raises(RuntimeError, match="SHA256"):
            verify_backup(path)
        destination.assert_not_called()


def test_existing_backup_is_not_overwritten(tmp_path):
    """Ni un archivo ni su recibo pueden perderse por ejecutar otra vez el backup."""
    path = tmp_path / "backup.rdb"
    path.write_bytes(b"existing-backup")
    with pytest.raises(FileExistsError):
        create_backup(RedisConfig(), path)
    assert path.read_bytes() == b"existing-backup"


def test_retaining_a_destination_requires_a_persistent_secret():
    """Una restauración durable no puede depender de un secreto que se va a borrar."""
    sandbox = RedisSandbox()
    try:
        with pytest.raises(RuntimeError, match="secreto permanente"):
            sandbox.retain()
    finally:
        sandbox.close()
