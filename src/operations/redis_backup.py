"""Backup RDB privado, comprobación de restauración y recuperación en volumen nuevo."""

import argparse
import json
import os
import shutil
import subprocess  # ruff: ignore[suspicious-subprocess-import] - redis-cli local, sin shell ni secretos en argumentos.
import tempfile
import time
from base64 import b64encode
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any, Literal, cast

from redis import Redis
from src.config.config_manager import config_manager
from src.config.game_config import RedisConfig
from src.operations.ground_migration import ground_fingerprint
from src.operations.redis_persistence import require
from src.operations.redis_sandbox import RedisSandbox, docker
from src.utils.password_utils import hash_password, verify_password


def private_json(path: Path, value: dict[str, Any]) -> None:
    """Escribe un recibo 0600 sin sobrescribir otro existente."""
    descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(descriptor, "w") as target:
        json.dump(value, target, ensure_ascii=False, indent=2)
        target.write("\n")


def encoded(value: bytes) -> str:
    """Representación reversible y estable de valores binarios.

    Returns:
        Base64 ASCII.
    """
    return b64encode(value).decode("ascii")


def persistent_snapshot(client: Redis) -> dict[str, Any]:
    """Resume todos los DBs sin incluir valores ni claves en el recibo.

    Sólo se compara estado sin TTL; Redis conserva el vencimiento absoluto de
    las claves temporales, que pueden expirar durante la recuperación.

    Returns:
        Cantidad y digest canónico por DB para strings, hashes, listas, sets y zsets.

    Raises:
        ValueError: Si hay tipos ajenos al contrato de datos de pyao.
    """
    databases = sorted(int(name.removeprefix("db")) for name in client.info("keyspace"))
    result: dict[str, Any] = {}
    for database in databases:
        client.select(database)
        digest = sha256()
        count = 0
        for key in sorted(client.scan_iter()):
            if client.pttl(key) != -1:
                continue
            kind = client.type(key)
            value: Any
            if kind == b"string":
                value = encoded(cast("bytes", client.get(key)))
            elif kind == b"hash":
                value = [
                    (encoded(k), encoded(v))
                    for k, v in sorted(cast("dict[bytes, bytes]", client.hgetall(key)).items())
                ]
            elif kind == b"list":
                value = [encoded(v) for v in cast("list[bytes]", client.lrange(key, 0, -1))]
            elif kind == b"set":
                value = sorted(encoded(v) for v in cast("set[bytes]", client.smembers(key)))
            elif kind == b"zset":
                value = sorted(
                    (encoded(k), str(v))
                    for k, v in cast(
                        "list[tuple[bytes, float]]", client.zrange(key, 0, -1, withscores=True)
                    )
                )
            else:
                msg = "El backup contiene un tipo Redis fuera del contrato de pyao"
                raise ValueError(msg)
            record = [encoded(key), encoded(kind), value]
            digest.update(json.dumps(record, ensure_ascii=True, separators=(",", ":")).encode())
            digest.update(b"\n")
            count += 1
        if count:
            result[str(database)] = {"persistent_keys": count, "sha256": digest.hexdigest()}
    return result


@contextmanager
def load_snapshot(
    path: Path, *, password_file: Path | None = None, purpose: str = "validation"
) -> Iterator[RedisSandbox]:
    """Carga RDB en un volumen nuevo y confirma su conversión a AOF.

    Yields:
        Redis restaurado aislado; se retira al salir salvo entrega explícita al operador.

    Raises:
        TimeoutError: Si la conversión a AOF no termina dentro del plazo.
    """
    role: Literal["validation", "recovery"] = "recovery" if purpose == "recovery" else "validation"
    with RedisSandbox(appendonly=False, password_file=password_file, purpose=role) as sandbox:
        docker("stop", "--time", "5", sandbox.name)
        docker("cp", str(path.resolve()), f"{sandbox.name}:/data/dump.rdb")
        docker("start", sandbox.name)
        with sandbox.client() as client:
            client.config_set("appendonly", "yes")
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                info = client.info("persistence")
                if not info["aof_rewrite_in_progress"] and not info["aof_rewrite_scheduled"]:
                    require(info["aof_last_bgrewrite_status"] == "ok", "rewrite del backup")
                    break
                time.sleep(0.05)
            else:
                msg = "La conversión del backup a AOF excedió el plazo"
                raise TimeoutError(msg)
            require(client.execute_command("WAITAOF", 1, 0, 5000)[0] == 1, "fsync del backup")
        sandbox.recreate(appendonly=True)
        yield sandbox


def manifest_for(path: Path) -> dict[str, Any]:
    """Comprueba el recibo y digest antes de crear o tocar un destino.

    Returns:
        Metadatos verificados.
    """
    manifest = cast(
        "dict[str, Any]", json.loads(path.with_suffix(path.suffix + ".json").read_text())
    )
    require(manifest["format"] == 1, "formato de recibo")
    require(sha256(path.read_bytes()).hexdigest() == manifest["sha256"], "SHA256 del backup")
    return manifest


def create_backup(settings: RedisConfig, destination: Path) -> dict[str, Any]:
    """Descarga un RDB consistente y lo publica sólo tras restaurarlo y comprobarlo.

    Returns:
        Recibo con versión, digest y resumen del estado persistente.

    Raises:
        FileExistsError: Si el destino o su recibo ya existen.
        RuntimeError: Si no está instalado redis-cli.
    """
    destination = destination.resolve()
    receipt = destination.with_suffix(destination.suffix + ".json")
    if destination.exists() or receipt.exists():
        raise FileExistsError(destination)
    executable = shutil.which("redis-cli")
    if executable is None:
        msg = "Se requiere redis-cli para crear un RDB consistente"
        raise RuntimeError(msg)
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor, name = tempfile.mkstemp(prefix=".pyao-backup-", dir=destination.parent)
    os.close(descriptor)
    temporary = Path(name)
    try:
        password = settings.read_password()
        environment = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "LC_ALL": "C"}
        if password is not None:
            environment["REDISCLI_AUTH"] = password
        with Redis(
            host=settings.host, port=settings.port, password=password, decode_responses=True
        ) as source:
            version = source.info("server")["redis_version"]
        subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true] - ejecutable resuelto, auth por entorno y argumentos separados.
            [executable, "-h", settings.host, "-p", str(settings.port), "--rdb", str(temporary)],
            env=environment,
            check=True,
            capture_output=True,
            timeout=60,
        )
        temporary.chmod(0o600)
        with (
            load_snapshot(temporary) as restored,
            restored.client(decode_responses=False) as client,
        ):
            snapshot = persistent_snapshot(client)
        manifest = {
            "format": 1,
            "created_at": datetime.now(UTC).isoformat(),
            "redis_version": version,
            "sha256": sha256(temporary.read_bytes()).hexdigest(),
            "persistent_state": snapshot,
        }
        os.link(temporary, destination)  # Publicación exclusiva, nunca reemplazar otro backup.
        private_json(receipt, manifest)
        return manifest
    finally:
        temporary.unlink(missing_ok=True)


def verify_backup(
    path: Path, *, password_file: Path | None = None, retain: bool = False
) -> dict[str, Any]:
    """Restaura en recursos nuevos y opcionalmente entrega ese destino al operador.

    Returns:
        Recibo de verificación y, al conservar, endpoint/volumen sin el secreto.
    """
    manifest = manifest_for(path)
    with load_snapshot(
        path, password_file=password_file, purpose="recovery" if retain else "validation"
    ) as restored:
        with restored.client(decode_responses=False) as client:
            require(
                persistent_snapshot(client) == manifest["persistent_state"], "estado restaurado"
            )
            ground_state = ground_fingerprint(client)
        result = {
            "verified": True,
            "persistent_state": manifest["persistent_state"],
            "source_modified": False,
            "ground_state": ground_state,
        }
        if retain:
            result.update(
                container=restored.name,
                volume=restored.volume,
                host="127.0.0.1",
                port=restored.port,
                password_file=str(restored.password_file),
            )
            restored.retain()
        return result


def selftest() -> dict[str, Any]:
    """Ensaya cuenta, economía, inventario, progreso, otro DB y rechazo de corrupción.

    Returns:
        Evidencia resumida; no incluye valores del fixture.

    Raises:
        RuntimeError: Si la validación acepta un backup corrupto.
    """
    with (
        RedisSandbox() as source,
        tempfile.TemporaryDirectory(prefix="pyao-backup-test-") as directory,
    ):
        with source.client() as client:
            canary = "SyntheticBackup107"
            client.hset(
                "account:backup:data",
                mapping={
                    "user_id": "1",
                    "username": "BackupTest",
                    "email": "backup@example.invalid",
                    "password_hash": hash_password(canary),
                    "char_race": "1",
                    "char_job": "1",
                },
            )
            client.hset(
                "player:1:stats", mapping={"gold": "1234", "level": "7", "experience": "431"}
            )
            client.hset("player:1:inventory", mapping={"slot_30": "1:2"})
            client.hset("player:1:skills", mapping={"points": "4", "skill_1": "37"})
            client.select(1)
            client.set("validation:other-db", "preserved")
        path = Path(directory) / "backup.rdb"
        settings = RedisConfig(
            host="127.0.0.1", port=source.port, password_file=source.password_file
        )
        create_backup(settings, path)
        verify_backup(path)
        with load_snapshot(path) as restored, restored.client() as recovered:
            require(
                verify_password(canary, recovered.hget("account:backup:data", "password_hash")),
                "contraseña de cuenta restaurada",
            )
            require(
                recovered.hget("player:1:inventory", "slot_30") == "1:2", "inventario restaurado"
            )
            require(recovered.hget("player:1:skills", "points") == "4", "progreso restaurado")
        with path.open("ab") as target:
            target.write(b"corrupt")
        try:
            verify_backup(path)
        except RuntimeError:
            pass
        else:
            msg = "Se aceptó un backup con digest incorrecto"
            raise RuntimeError(msg)
        with source.client() as client:
            require(client.hget("player:1:stats", "gold") == "1234", "origen intacto")
        return {
            "backup_created": True,
            "restoration_verified": True,
            "restored_password_verified": True,
            "corruption_rejected": True,
            "source_modified": False,
            "production_data_used": False,
        }


def main() -> None:
    """Interfaz uv para backup, verificación y restauración en un volumen nuevo."""
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    backup = commands.add_parser("backup")
    backup.add_argument("--output", type=Path, required=True)
    backup.add_argument("--host")
    backup.add_argument("--port", type=int)
    backup.add_argument("--password-file", type=Path)
    verify = commands.add_parser("verify")
    verify.add_argument("path", type=Path)
    restore = commands.add_parser("restore")
    restore.add_argument("path", type=Path)
    restore.add_argument("--password-file", type=Path, required=True)
    commands.add_parser("selftest")
    args = parser.parse_args()
    if args.command == "backup":
        values = config_manager.get_section("redis").copy()
        values.update(
            {
                name: getattr(args, name)
                for name in ["host", "port", "password_file"]
                if getattr(args, name) is not None
            }
        )
        result = create_backup(RedisConfig.model_validate(values), args.output)
    elif args.command == "selftest":
        result = selftest()
    else:
        result = verify_backup(
            args.path,
            password_file=getattr(args, "password_file", None),
            retain=args.command == "restore",
        )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
