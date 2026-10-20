"""Migración offline de suelo JSON a hash, sin alterar IDs, metadatos ni vencimientos."""

import json
import time
from dataclasses import dataclass
from hashlib import sha256
from typing import TYPE_CHECKING, Any, cast

from src.core.schema_manager import SchemaMigrationError
from src.utils.ground_state import GroundState
from src.utils.ground_storage import encode_fields, map_id_from_key, validate_fields

if TYPE_CHECKING:
    from collections.abc import Mapping

    from redis.client import Pipeline
    from redis.typing import EncodableT

    from redis import Redis

REDIS_KEY_ABSENT = -2


@dataclass(frozen=True, slots=True)
class GroundRewrite:
    """Fuente revalidable y vencimiento absoluto del mapa que se convierte."""

    source: str
    fields: dict[str, str]
    expires_at: int


def ground_rewrites(client: Redis) -> dict[str, GroundRewrite]:
    """Valida íntegramente cada mapa antes de encolar la primera escritura.

    Returns:
        Conversiones estables para revalidar bajo WATCH.

    Raises:
        SchemaMigrationError: Si hay claves, tipos, casillas o stacks inválidos.
    """
    result = {}
    for name in sorted(client.scan_iter(match="ground_items:*")):
        key = name.decode() if isinstance(name, bytes) else name
        map_id = map_id_from_key(key)
        if not map_id:
            message = "Clave de suelo inválida; reparar antes de migrar"
            raise SchemaMigrationError(message)
        kind = client.type(key)
        if kind in {"none", b"none"}:
            continue
        if kind not in {"string", b"string"}:
            message = "El suelo legado no es JSON; no se reemplaza durante la migración"
            raise SchemaMigrationError(message)
        raw = client.get(key)
        expires_at = int(client.pexpiretime(key))
        if raw is None or expires_at == REDIS_KEY_ABSENT:
            continue
        text = raw.decode() if isinstance(raw, bytes) else raw
        try:
            ground = GroundState(map_id, text)
            validate_fields(ground)
        except (TypeError, ValueError) as error:
            message = "Suelo inválido; migración cancelada sin reemplazar datos"
            raise SchemaMigrationError(message) from error
        fields = {
            field: value for field, value in encode_fields(ground).items() if ground.tiles[field]
        }
        result[key] = GroundRewrite(text, fields, expires_at)
    return result


def enqueue_ground_rewrites(pipe: Pipeline, rewrites: dict[str, GroundRewrite]) -> None:
    """Cambia tipos y conserva PEXPIRETIME en el mismo EXEC que el esquema."""
    for key, rewrite in rewrites.items():
        pipe.delete(key)
        if rewrite.fields:
            pipe.hset(key, mapping=cast("Mapping[EncodableT, EncodableT]", rewrite.fields))
            if rewrite.expires_at > 0:
                pipe.pexpireat(key, rewrite.expires_at)


def ground_fingerprint(client: Redis) -> dict[str, Any]:
    """Incluye suelo con TTL al comparar un RDB y el origen antes de migrar.

    Returns:
        Hashes y vencimientos por DB, sin objetos ni valores de jugadores.

    Raises:
        SchemaMigrationError: Si el respaldo contiene un tipo de suelo ajeno al contrato.
    """
    result: dict[str, Any] = {}
    original_db = int(client.connection_pool.connection_kwargs.get("db", 0))
    try:
        databases = sorted(int(name.removeprefix("db")) for name in client.info("keyspace"))
        for database in databases:
            client.select(database)
            maps = {}
            for name in sorted(client.scan_iter(match="ground_items:*")):
                key = name.decode() if isinstance(name, bytes) else name
                kind = client.type(key)
                expires_at = int(client.pexpiretime(key))
                if kind in {"none", b"none"} or expires_at == REDIS_KEY_ABSENT:
                    continue
                content: Any
                if kind in {"string", b"string"}:
                    value = client.get(key)
                    content = value.decode() if isinstance(value, bytes) else value
                elif kind in {"hash", b"hash"}:
                    rows = client.hgetall(key)
                    content = {
                        field.decode() if isinstance(field, bytes) else field: value.decode()
                        if isinstance(value, bytes)
                        else value
                        for field, value in rows.items()
                    }
                else:
                    message = "Tipo de suelo inválido en el backup"
                    raise SchemaMigrationError(message)
                encoded = json.dumps(content, sort_keys=True, separators=(",", ":"))
                maps[key] = {
                    "sha256": sha256(encoded.encode()).hexdigest(),
                    "expires_at": expires_at,
                }
            if maps:
                result[str(database)] = maps
    finally:
        client.select(original_db)
    return active_ground_fingerprint(result)


def active_ground_fingerprint(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Excluye sólo el suelo que ya venció naturalmente al comparar snapshots.

    Returns:
        Resumen vigente, sin prolongar la vida del suelo respaldado.
    """
    now = int(time.time() * 1000)
    result = {}
    for database, maps in snapshot.items():
        active = {
            key: value
            for key, value in maps.items()
            if value["expires_at"] == -1 or value["expires_at"] > now
        }
        if active:
            result[database] = active
    return result
