"""Migraciones ordenadas del estado persistido con backup verificado y reserva propia."""

import argparse
import json
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from secrets import token_urlsafe
from typing import Any, cast

from redis.exceptions import WatchError

from redis import Redis
from src.config.config_manager import config_manager
from src.config.game_config import RedisConfig
from src.core.schema_manager import (
    CURRENT_SCHEMA_VERSION,
    MIGRATION_LOCK_KEY,
    MIGRATIONS,
    SCHEMA_KEY,
    SchemaMigrationError,
    parse_version,
)
from src.operations.redis_backup import (
    create_backup,
    manifest_for,
    persistent_snapshot,
    verify_backup,
)
from src.operations.redis_persistence import require
from src.operations.redis_sandbox import RedisSandbox


def connection(settings: RedisConfig, *, binary: bool = False) -> Redis:
    """Construye un cliente administrativo con endpoint, secreto y timeouts centrales.

    Returns:
        Cliente del origen elegido por el operador.
    """
    return Redis(
        host=settings.host,
        port=settings.port,
        db=settings.db,
        password=settings.read_password(),
        decode_responses=not binary,
        socket_timeout=settings.socket_timeout,
        socket_connect_timeout=settings.socket_connect_timeout,
    )


def version_of(client: Redis) -> int:
    """Lee la versión seleccionada sin modificar datos.

    Returns:
        Versión validada del esquema.
    """
    return parse_version(cast("str | bytes | None", client.hget(SCHEMA_KEY, "version")))


def release_lock(client: Redis, token: str) -> None:
    """Libera sólo la reserva propia mediante comparación y transacción."""
    for _ in range(3):
        with client.pipeline() as pipe:
            try:
                pipe.watch(MIGRATION_LOCK_KEY)  # type: ignore[no-untyped-call]
                if pipe.get(MIGRATION_LOCK_KEY) != token:
                    return
                pipe.multi()
                pipe.delete(MIGRATION_LOCK_KEY)
                pipe.execute()
            except WatchError:
                continue
            else:
                return


def apply_ordered_steps(client: Redis, token: str, backup_digest: str) -> list[str]:
    """Confirma cada paso y su versión/journal como un único HSET.

    Returns:
        Nombres de pasos efectivamente aplicados, en orden.

    Raises:
        SchemaMigrationError: Si se pierde la reserva o hay una carrera persistente.
    """
    applied = []
    for target, name in sorted(MIGRATIONS.items()):
        for _ in range(3):
            with client.pipeline() as pipe:
                try:
                    pipe.watch(SCHEMA_KEY, MIGRATION_LOCK_KEY)  # type: ignore[no-untyped-call]
                    if pipe.get(MIGRATION_LOCK_KEY) != token:
                        msg = "La migración perdió su reserva; no se modifica el estado"
                        raise SchemaMigrationError(msg)
                    current = parse_version(
                        cast("str | bytes | None", pipe.hget(SCHEMA_KEY, "version"))
                    )
                    if current >= target:
                        break
                    require(current == target - 1, "orden de migraciones")
                    # v1 adopta el layout existente. No normaliza ni reinicializa progreso.
                    entry = json.dumps(
                        {
                            "name": name,
                            "from": current,
                            "to": target,
                            "backup_sha256": backup_digest,
                            "applied_at": datetime.now(UTC).isoformat(),
                        }
                    )
                    pipe.multi()
                    pipe.hset(
                        SCHEMA_KEY, mapping={"version": str(target), f"migration:{target}": entry}
                    )
                    pipe.execute()
                    applied.append(name)
                    break
                except WatchError:
                    continue
        else:
            msg = "No se pudo confirmar el paso de migración"
            raise SchemaMigrationError(msg)
    return applied


def migrate(settings: RedisConfig, backup: Path) -> dict[str, Any]:
    """Migra sólo con respaldo restaurable y el origen todavía igual al backup.

    Returns:
        Versiones y pasos, sin datos de jugadores ni credenciales.

    Raises:
        SchemaMigrationError: Si el juego sigue activo o existe otra migración.
    """
    with connection(settings) as client:
        initial = version_of(client)
        # Verifica AOF antes de cualquier cambio y confirma también reintentos idempotentes.
        require(client.execute_command("WAITAOF", 1, 0, 5000)[0] == 1, "AOF disponible para migrar")
        if initial == CURRENT_SCHEMA_VERSION:
            return {"from": initial, "to": initial, "applied": []}
        if next(client.scan_iter(match="session:*:owner"), None) is not None:
            msg = "Detener el juego y esperar la liberación/expiración de sesiones antes de migrar"
            raise SchemaMigrationError(msg)
        manifest = manifest_for(backup)
        verify_backup(backup)
        token = token_urlsafe(32)
        if not client.set(MIGRATION_LOCK_KEY, token, nx=True, ex=300):
            msg = "Otro proceso está migrando Redis"
            raise SchemaMigrationError(msg)
        try:
            with connection(settings, binary=True) as binary:
                require(
                    persistent_snapshot(binary) == manifest["persistent_state"],
                    "origen cambiado desde el backup",
                )
            applied = apply_ordered_steps(client, token, manifest["sha256"])
            require(client.execute_command("WAITAOF", 1, 0, 5000)[0] == 1, "fsync de migración")
            return {"from": initial, "to": version_of(client), "applied": applied}
        finally:
            release_lock(client, token)


def selftest() -> dict[str, Any]:
    """Adopta un fixture legado con respaldo real sin alterar su progreso.

    Returns:
        Evidencia de conservación, idempotencia y rechazo de versiones futuras.

    Raises:
        RuntimeError: Si una versión futura se acepta o cambia el progreso.
    """
    with (
        RedisSandbox() as sandbox,
        tempfile.TemporaryDirectory(prefix="pyao-migration-") as directory,
    ):
        settings = RedisConfig(
            host="127.0.0.1", port=sandbox.port, password_file=sandbox.password_file
        )
        with sandbox.client() as client:
            client.hset(
                "account:migration:data", mapping={"user_id": "1", "username": "MigrationTest"}
            )
            client.hset(
                "player:1:stats", mapping={"gold": "1234", "level": "7", "experience": "431"}
            )
            client.hset("player:1:inventory", mapping={"slot_30": "1:2"})
            client.hset("player:1:skills", mapping={"points": "4", "skill_1": "37"})
        path = Path(directory) / "before.rdb"
        create_backup(settings, path)
        require(migrate(settings, path)["applied"] == ["adopt-legacy-layout"], "paso v1")
        require(migrate(settings, path)["applied"] == [], "reintento idempotente")
        with sandbox.client() as client:
            require(client.hget("player:1:stats", "gold") == "1234", "oro preservado")
            require(client.hget("player:1:inventory", "slot_30") == "1:2", "objetos preservados")
            require(client.hget("player:1:skills", "points") == "4", "progreso preservado")
            client.hset(SCHEMA_KEY, "version", str(CURRENT_SCHEMA_VERSION + 1))
        try:
            migrate(settings, path)
        except SchemaMigrationError:
            pass
        else:
            msg = "Se aceptó una versión futura incompatible"
            raise RuntimeError(msg)
        return {
            "legacy_migrated": True,
            "progress_preserved": True,
            "idempotent": True,
            "future_rejected": True,
            "production_data_used": False,
        }


def main() -> None:
    """Ejecuta status/migrate/selftest con uv y la configuración central."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["status", "migrate", "selftest"])
    parser.add_argument("--backup", type=Path)
    args = parser.parse_args()
    if args.command == "selftest":
        result = selftest()
    else:
        settings = RedisConfig.model_validate(config_manager.get_section("redis"))
        if args.command == "status":
            with connection(settings) as client:
                result = {"current": version_of(client), "supported": CURRENT_SCHEMA_VERSION}
        else:
            if args.backup is None:
                parser.error("migrate requiere --backup <archivo.rdb> previamente verificado")
            result = migrate(settings, args.backup)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
