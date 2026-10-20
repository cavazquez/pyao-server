"""Migraciones ordenadas del estado persistido con backup verificado y reserva propia."""

import argparse
import json
import os
import shutil
import subprocess  # ruff: ignore[suspicious-subprocess-import] - intérprete propio sin shell y con configuración temporal.
import sys
import tempfile
import tomllib
from datetime import UTC, datetime
from pathlib import Path
from secrets import token_urlsafe
from typing import TYPE_CHECKING, Any, cast

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
from src.economy.tax_migration import tax_repairs
from src.economy.taxes import utc_day
from src.operations.ground_migration import (
    active_ground_fingerprint,
    enqueue_ground_rewrites,
    ground_fingerprint,
    ground_rewrites,
)
from src.operations.mana_repair import mana_repairs
from src.operations.redis_backup import (
    create_backup,
    load_snapshot,
    manifest_for,
    persistent_snapshot,
    verify_backup,
)
from src.operations.redis_persistence import require
from src.operations.redis_sandbox import RedisSandbox
from src.operations.skill_migration import skill_repairs
from src.runtime_paths import resource_root
from src.utils.ground_state import GroundState
from src.utils.ground_storage import decode_fields
from src.utils.password_utils import hash_password, verify_password
from tools.compression.decompress_map_data import decompress_map_data

if TYPE_CHECKING:
    from collections.abc import Mapping

    from redis.typing import EncodableT


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
    return parse_version(client.hget(SCHEMA_KEY, "version"))


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


MANA_SCHEMA_VERSION = 2
SKILL_SCHEMA_VERSION = 4
TAX_SCHEMA_VERSION = 5
GROUND_SCHEMA_VERSION = 6


def migration_fields(
    client: Redis, current: int, *, day: int | None = None
) -> dict[str, dict[str, str]]:
    """Calcula todos los campos que se van a confirmar juntos.

    Returns:
        Cambios de maná/progreso pendientes según la versión de origen.
    """
    result = mana_repairs(client) if current < MANA_SCHEMA_VERSION else {}
    if current < SKILL_SCHEMA_VERSION:
        result.update(skill_repairs(client))
    if current < TAX_SCHEMA_VERSION:
        result.update(tax_repairs(client, utc_day() if day is None else day))
    return result


def apply_ordered_steps(client: Redis, token: str, backup_digest: str) -> list[str]:
    """Confirma los pasos pendientes y sus journals en una sola transacción.

    Returns:
        Nombres de pasos aplicados, en orden; vacío al repetir una confirmación.

    Raises:
        SchemaMigrationError: Si se pierde la reserva o hay una carrera persistente.
    """
    migration_day = utc_day()
    for _ in range(3):
        with client.pipeline() as pipe:
            try:
                pipe.watch(SCHEMA_KEY, MIGRATION_LOCK_KEY)  # type: ignore[no-untyped-call]
                if pipe.get(MIGRATION_LOCK_KEY) != token:
                    msg = "La migración perdió su reserva; no se modifica el estado"
                    raise SchemaMigrationError(msg)
                current = parse_version(pipe.hget(SCHEMA_KEY, "version"))
                pending = [
                    (target, name)
                    for target, name in sorted(MIGRATIONS.items())
                    if target > current
                ]
                if not pending:
                    return []
                repairs = migration_fields(client, current, day=migration_day)
                ground = ground_rewrites(client) if current < GROUND_SCHEMA_VERSION else {}
                if ground:
                    pipe.watch(*ground)  # type: ignore[no-untyped-call]
                    if ground_rewrites(client) != ground:
                        continue
                if repairs:
                    pipe.watch(*repairs)  # type: ignore[no-untyped-call]
                    revalidated = migration_fields(client, current, day=migration_day)
                    if revalidated.keys() != repairs.keys():
                        continue
                    repairs = revalidated
                pipe.multi()
                if current < TAX_SCHEMA_VERSION:
                    pipe.set("config:effects:gold_decay:enabled", "0")
                for key, fields in repairs.items():
                    pipe.hset(key, mapping=cast("Mapping[EncodableT, EncodableT]", fields))
                enqueue_ground_rewrites(pipe, ground)
                for target, name in pending:
                    require(current == target - 1, "orden de migraciones")
                    entry = json.dumps(
                        {
                            "name": name,
                            "from": current,
                            "to": target,
                            "backup_sha256": backup_digest,
                            "applied_at": datetime.now(UTC).isoformat(),
                            "changed_hashes": len(repairs),
                            "ground_maps": len(ground),
                        }
                    )
                    pipe.hset(
                        SCHEMA_KEY, mapping={"version": str(target), f"migration:{target}": entry}
                    )
                    current = target
                pipe.execute()
                return [name for _, name in pending]
            except WatchError:
                continue
    msg = "No se pudo confirmar la migración"
    raise SchemaMigrationError(msg)


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
        verification = verify_backup(backup)
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
                require(
                    ground_fingerprint(binary)
                    == active_ground_fingerprint(verification["ground_state"]),
                    "suelo con TTL cambiado desde el backup",
                )
            applied = apply_ordered_steps(client, token, manifest["sha256"])
            require(client.execute_command("WAITAOF", 1, 0, 5000)[0] == 1, "fsync de migración")
            return {"from": initial, "to": version_of(client), "applied": applied}
        finally:
            release_lock(client, token)


def legacy_config_check(directory: Path) -> None:
    """Ensaya consulta sin Redis y reparación explícita respaldada de un TOML propio."""
    path = directory / "server.toml"
    maps = directory / "maps"
    decompress_map_data(resource_root() / "archives/map_data.xz", maps, overwrite=False)
    legacy = "[game.character]\nmana_per_int = 50000\n[server]\nport = 17777\n"
    path.write_text(legacy)
    environment = {k: v for k, v in os.environ.items() if not k.startswith("PYAO_")}
    environment.update(
        PYAO_CONFIG_FILE=str(path),
        PYAO_REDIS__HOST="unreachable.invalid",
        PYAO_REDIS__PASSWORD_FILE=str(directory / "missing-secret"),
        PYAO_MAPS_DIR=str(maps),
        PYAO_DATA_DIR=str(resource_root() / "data"),
        PYAO_STATE_DIR=str(directory / "state"),
    )
    for flag in ("--version", "--help", None):
        result = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true] - intérprete actual y argumentos propios.
            [sys.executable, "-m", "src.run_server", *([flag] if flag else [])],
            env=environment,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if flag is None:
            require(result.returncode != 0 and "mana_per_int" in result.stderr, "rechazo TOML")
        else:
            require(result.returncode == 0, "consulta CLI sin Redis ni TOML válido")
        require(path.read_text() == legacy, "configuración conservada")
    backup = path.with_suffix(".toml.bak")
    shutil.copyfile(path, backup)
    path.write_text(legacy.replace("mana_per_int = 50000", "mana_per_int = 10"))
    from src.config.game_config import GameConfig  # ruff: ignore[import-outside-top-level]

    repaired_mana = 10
    require(
        GameConfig.from_toml(path).game.character.mana_per_int == repaired_mana,
        "reparación explícita",
    )
    require(backup.read_text() == legacy, "respaldo anterior a reparación")
    require(
        GameConfig.from_toml(path).server.port
        == tomllib.loads(backup.read_text())["server"]["port"],
        "opciones propias conservadas",
    )


def check_legacy_progress(client: Redis, fixture: dict[str, Any], password: str) -> None:
    """Comprueba todos los campos heredados salvo la reparación de maná documentada."""
    for key, value in fixture["strings"].items():
        require(client.get(key) == value, "índices y oro bancario preservados")
    for key, values in fixture["hashes"].items():
        for field, value in values.items():
            if key.endswith(":user_stats") and field in {"min_mana", "max_mana"}:
                continue
            require(client.hget(key, field) == value, "cuenta y progreso heredados preservados")
    stored = cast("str", client.hget("account:MigrationTest:data", "password_hash"))
    require(verify_password(password, stored), "contraseña válida tras migración/restauración")


def selftest() -> dict[str, Any]:  # ruff: ignore[too-many-statements] - Ensayo secuencial de backup, migración, AOF y reversión.
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
        legacy_config_check(Path(directory))
        fixture_path = resource_root() / "data/validation/redis_upgrade.toml"
        fixture = tomllib.loads(fixture_path.read_text())
        password = token_urlsafe(32)
        settings = RedisConfig(
            host="127.0.0.1", port=sandbox.port, password_file=sandbox.password_file
        )
        with sandbox.client() as client:
            for key, value in fixture["strings"].items():
                client.set(key, value)
            for key, values in fixture["hashes"].items():
                client.hset(key, mapping=values)
            client.hset("account:MigrationTest:data", "password_hash", hash_password(password))
            legacy_ground = json.dumps(
                {
                    "50,50": [
                        {"item_id": 1, "quantity": 2, "owner_id": None, "grh_index": 3},
                        {
                            "item_id": 12,
                            "quantity": 1000,
                            "devaluation_day": 20000,
                            "devaluation_remainder": 9000,
                        },
                    ]
                }
            )
            expected_ground = GroundState(1, legacy_ground)
            client.set("ground_items:1", legacy_ground, px=500000)
            ground_expiry = client.pexpiretime("ground_items:1")
        path = Path(directory) / "before.rdb"
        backup = create_backup(settings, path)
        with sandbox.client() as client:
            client.set("ground_items:1", "{}", keepttl=True)
        try:
            migrate(settings, path)
        except RuntimeError as error:
            require("suelo con TTL" in str(error), "rechazo del suelo modificado tras backup")
        else:
            message = "Se migró suelo con TTL distinto al respaldo"
            raise RuntimeError(message)
        with sandbox.client() as client:
            require(not client.exists(SCHEMA_KEY), "rechazo antes de cambiar esquema")
            client.set("ground_items:1", legacy_ground, keepttl=True)
        require(migrate(settings, path)["applied"] == list(MIGRATIONS.values()), "pasos ordenados")
        require(migrate(settings, path)["applied"] == [], "reintento idempotente")
        with sandbox.client() as client:
            check_legacy_progress(client, fixture, password)
            require(
                decode_fields(1, client.hgetall("ground_items:1")).tiles == expected_ground.tiles,
                "suelo e identidades conservados",
            )
            require(
                client.pexpiretime("ground_items:1") == ground_expiry, "TTL absoluto conservado"
            )
            migrated_ground = ground_fingerprint(client)
            require(client.hget("player:1:stats", "gold") == "1234", "oro preservado")
            require(
                client.hmget("player:1:user_stats", "min_mana", "max_mana") == ["32767", "32767"],
                "maná reparado",
            )
            require(
                client.hget("player:1:user_stats", "migration:mana:maximum_before") == "500000",
                "auditoría de maná",
            )
            require(client.hget("player:1:inventory", "slot_30") == "1:2", "objetos preservados")
            require(client.hget("player:1:skills", "points") == "4", "progreso preservado")
            require(
                client.hmget("player:1:skills", ["level:magia", "level:talar", "xp:talar", "talar"])
                == ["10", "2", "275", "275"],
                "XP/nivel separados sin borrar legado",
            )
        with sandbox.client(decode_responses=False) as client:
            migrated = persistent_snapshot(client)
        sandbox.recreate(appendonly=True)
        settings = settings.model_copy(update={"port": sandbox.port})
        require(migrate(settings, path)["applied"] == [], "idempotencia tras reinicio")
        with sandbox.client(decode_responses=False) as client:
            require(persistent_snapshot(client) == migrated, "reinicio tras migración")
            require(ground_fingerprint(client) == migrated_ground, "suelo con TTL tras reinicio")
        with load_snapshot(path) as restored:
            with restored.client(decode_responses=False) as client:
                require(
                    persistent_snapshot(client) == backup["persistent_state"], "rollback íntegro"
                )
            with restored.client() as client:
                check_legacy_progress(client, fixture, password)
                require(client.get("ground_items:1") == legacy_ground, "rollback de suelo completo")
                require(client.pexpiretime("ground_items:1") == ground_expiry, "TTL del rollback")
                require(not client.exists(SCHEMA_KEY), "rollback al esquema legado")
                require(
                    client.hget("player:1:user_stats", "max_mana") == "500000",
                    "rollback conserva valores previos a reparación",
                )
        with sandbox.client() as client:
            check_legacy_progress(client, fixture, password)
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
            "mana_repaired_with_audit": True,
            "ground_hash_preserved": True,
            "ground_expiry_preserved": True,
            "ground_rollback_preserved": True,
            "backup_checks_expiring_ground": True,
            "skill_progress_preserved": True,
            "idempotent": True,
            "restart_preserved": True,
            "rollback_verified": True,
            "legacy_config_checked": True,
            "bank_and_spell_order_preserved": True,
            "account_password_verified": True,
            "fixture": "data/validation/redis_upgrade.toml",
            "fixture_kind": "representative-legacy-schema-not-running-0.9.4",
            "backup_sha256": backup["sha256"],
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
                result = {
                    "current": version_of(client),
                    "supported": CURRENT_SCHEMA_VERSION,
                    "mana_out_of_range": len(mana_repairs(client)),
                }
        else:
            if args.backup is None:
                parser.error("migrate requiere --backup <archivo.rdb> previamente verificado")
            result = migrate(settings, args.backup)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
