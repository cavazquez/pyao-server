"""Herramienta para sincronizar map_data con archives/map_data.xz.

Comandos:
    status  - Muestra el estado de sincronización
    pull    - Descomprime archives/map_data.xz a map_data/
    push    - Comprime map_data/ a archives/map_data.xz
"""
# ruff: noqa: DOC201, TRY300, BLE001

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path

from tools.compression.compress_map_data import compress_map_data
from tools.compression.decompress_map_data import decompress_map_data

logger = logging.getLogger(__name__)

DEFAULT_ARCHIVE = Path("archives/map_data.xz")
DEFAULT_MAP_DATA = Path("map_data")
SYNC_METADATA_FILE = ".map_sync_metadata.json"


class SyncStatus(Enum):
    """Estado de sincronización entre map_data y archive."""

    NO_MAP_DATA = "no_map_data"
    NO_ARCHIVE = "no_archive"
    IN_SYNC = "in_sync"
    LOCAL_CHANGES = "local_changes"
    ARCHIVE_NEWER = "archive_newer"
    CONFLICT = "conflict"


@dataclass
class SyncInfo:
    """Información de sincronización."""

    status: SyncStatus
    archive_mtime: float | None = None
    last_decompress: float | None = None
    newest_local_file: str | None = None
    newest_local_mtime: float | None = None
    message: str = ""


def get_metadata_path(map_data_dir: Path) -> Path:
    """Retorna la ruta del archivo de metadatos de sincronización."""
    return map_data_dir / SYNC_METADATA_FILE


def read_sync_metadata(map_data_dir: Path) -> dict:
    """Lee los metadatos de sincronización."""
    metadata_path = get_metadata_path(map_data_dir)
    if not metadata_path.exists():
        return {}
    try:
        with metadata_path.open() as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def write_sync_metadata(map_data_dir: Path, metadata: dict) -> None:
    """Escribe los metadatos de sincronización."""
    metadata_path = get_metadata_path(map_data_dir)
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    with metadata_path.open("w") as f:
        json.dump(metadata, f, indent=2)


def get_newest_file_in_dir(directory: Path) -> tuple[Path | None, float]:
    """Encuentra el archivo más recientemente modificado en un directorio."""
    newest_path: Path | None = None
    newest_mtime: float = 0

    if not directory.exists():
        return None, 0

    for file_path in directory.rglob("*"):
        if file_path.is_file() and file_path.name != SYNC_METADATA_FILE:
            try:
                mtime = file_path.stat().st_mtime
                if mtime > newest_mtime:
                    newest_mtime = mtime
                    newest_path = file_path
            except OSError:
                continue

    return newest_path, newest_mtime


def get_sync_status(
    archive_path: Path = DEFAULT_ARCHIVE,
    map_data_dir: Path = DEFAULT_MAP_DATA,
) -> SyncInfo:
    """Determina el estado de sincronización entre map_data y archive."""
    archive_exists = archive_path.exists()
    map_data_exists = map_data_dir.exists() and any(map_data_dir.iterdir())

    if not map_data_exists:
        if not archive_exists:
            return SyncInfo(
                status=SyncStatus.NO_ARCHIVE,
                message="No existe ni map_data/ ni archives/map_data.xz",
            )
        return SyncInfo(
            status=SyncStatus.NO_MAP_DATA,
            archive_mtime=archive_path.stat().st_mtime,
            message="map_data/ no existe. Ejecuta 'map_sync pull' para descomprimir.",
        )

    if not archive_exists:
        newest_file, newest_mtime = get_newest_file_in_dir(map_data_dir)
        return SyncInfo(
            status=SyncStatus.NO_ARCHIVE,
            newest_local_file=str(newest_file) if newest_file else None,
            newest_local_mtime=newest_mtime,
            message="archives/map_data.xz no existe. Ejecuta 'map_sync push'.",
        )

    archive_mtime = archive_path.stat().st_mtime
    metadata = read_sync_metadata(map_data_dir)
    last_decompress = metadata.get("last_decompress", 0)
    newest_file, newest_local_mtime = get_newest_file_in_dir(map_data_dir)
    has_local_changes = newest_local_mtime > last_decompress if last_decompress else True
    archive_is_newer = archive_mtime > last_decompress if last_decompress else False

    info = SyncInfo(
        status=SyncStatus.IN_SYNC,
        archive_mtime=archive_mtime,
        last_decompress=last_decompress,
        newest_local_file=str(newest_file.relative_to(map_data_dir)) if newest_file else None,
        newest_local_mtime=newest_local_mtime,
    )

    if has_local_changes and archive_is_newer:
        info.status = SyncStatus.CONFLICT
        info.message = (
            "CONFLICTO: Hay cambios locales Y el archive fue actualizado.\n"
            "   - 'map_sync push' para guardar tus cambios\n"
            "   - 'map_sync pull --force' para descartar cambios locales"
        )
    elif has_local_changes:
        info.status = SyncStatus.LOCAL_CHANGES
        info.message = f"Cambios locales no comprimidos: {info.newest_local_file}"
    elif archive_is_newer:
        info.status = SyncStatus.ARCHIVE_NEWER
        info.message = "Archive es mas nuevo. Ejecuta 'map_sync pull'."
    else:
        info.status = SyncStatus.IN_SYNC
        info.message = "Sincronizado."

    return info


def format_timestamp(ts: float | None) -> str:
    """Formatea un timestamp Unix a string legible."""
    if ts is None or ts == 0:
        return "N/A"
    return datetime.fromtimestamp(ts, tz=UTC).strftime("%Y-%m-%d %H:%M:%S")


def cmd_status(args: argparse.Namespace) -> int:
    """Comando: muestra el estado de sincronización."""
    archive_path = Path(args.archive)
    map_data_dir = Path(args.map_data)
    info = get_sync_status(archive_path, map_data_dir)

    print("\n" + "=" * 60)
    print("  Estado de Sincronizacion de Mapas")
    print("=" * 60)
    print(f"  Archive:        {archive_path}")
    print(f"  Map Data:       {map_data_dir}")
    print("-" * 60)
    print(f"  Archive mtime:        {format_timestamp(info.archive_mtime)}")
    print(f"  Ultima descompresion: {format_timestamp(info.last_decompress)}")
    print(f"  Archivo mas nuevo:    {info.newest_local_file or 'N/A'}")
    print("-" * 60)
    print(f"\n{info.message}\n")

    return 0 if info.status == SyncStatus.IN_SYNC else 1


def cmd_pull(args: argparse.Namespace) -> int:
    """Comando: descomprime archive a map_data/."""
    archive_path = Path(args.archive)
    map_data_dir = Path(args.map_data)

    if not archive_path.exists():
        print(f"Error: No existe {archive_path}")
        return 1

    info = get_sync_status(archive_path, map_data_dir)

    if info.status in {SyncStatus.LOCAL_CHANGES, SyncStatus.CONFLICT}:
        if not args.force:
            print("\nHay cambios locales que se perderan:")
            print(f"   Archivo mas reciente: {info.newest_local_file}")
            print("\n   Usa --force para sobrescribir.\n")
            return 1
        print("Sobrescribiendo cambios locales (--force)")

    print(f"Descomprimiendo {archive_path} -> {map_data_dir}...")

    try:
        decompress_map_data(archive_path, map_data_dir, overwrite=True)
        write_sync_metadata(
            map_data_dir,
            {
                "last_decompress": time.time(),
                "archive_mtime": archive_path.stat().st_mtime,
            },
        )
        print("Descompresion completada.")
        return 0
    except Exception as e:
        print(f"Error durante descompresion: {e}")
        return 1


def cmd_push(args: argparse.Namespace) -> int:
    """Comando: comprime map_data/ a archive."""
    archive_path = Path(args.archive)
    map_data_dir = Path(args.map_data)

    if not map_data_dir.exists():
        print(f"Error: No existe {map_data_dir}")
        return 1

    info = get_sync_status(archive_path, map_data_dir)

    if info.status == SyncStatus.IN_SYNC and not args.force:
        print("Sincronizado. Nada que comprimir. Usa --force para forzar.")
        return 0

    print(f"Comprimiendo {map_data_dir} -> {archive_path}...")

    try:
        compress_map_data(map_data_dir, archive_path, level=args.level)
        write_sync_metadata(
            map_data_dir,
            {
                "last_decompress": time.time(),
                "archive_mtime": archive_path.stat().st_mtime,
            },
        )
        print("Compresion completada.")
        return 0
    except Exception as e:
        print(f"Error durante compresion: {e}")
        return 1


def check_map_sync_on_startup(
    archive_path: Path = DEFAULT_ARCHIVE,
    map_data_dir: Path = DEFAULT_MAP_DATA,
    auto_decompress: bool = True,
) -> bool:
    """Verifica sincronizacion al iniciar el servidor."""
    info = get_sync_status(archive_path, map_data_dir)

    if info.status == SyncStatus.NO_MAP_DATA:
        if auto_decompress:
            logger.info("map_data/ no existe. Descomprimiendo desde archive...")
            try:
                decompress_map_data(archive_path, map_data_dir, overwrite=False)
                write_sync_metadata(
                    map_data_dir,
                    {
                        "last_decompress": time.time(),
                        "archive_mtime": archive_path.stat().st_mtime,
                    },
                )
                logger.info("map_data/ creado desde archive")
                return True
            except Exception:
                logger.exception("Error descomprimiendo map_data")
                return False
        else:
            logger.warning(
                "map_data/ no existe. Ejecuta: uv run python -m tools.compression.map_sync pull"
            )
            return False

    if info.status == SyncStatus.NO_ARCHIVE:
        logger.warning("archives/map_data.xz no existe.")
        return map_data_dir.exists()

    if info.status == SyncStatus.LOCAL_CHANGES:
        logger.warning("Hay cambios locales en map_data/ no comprimidos.")
        return True

    if info.status == SyncStatus.ARCHIVE_NEWER:
        logger.warning("archives/map_data.xz es mas nuevo que map_data/.")
        return True

    if info.status == SyncStatus.CONFLICT:
        logger.warning("CONFLICTO: Cambios locales Y archive actualizado.")
        return True

    return True


def main() -> None:
    """Punto de entrada CLI."""
    parser = argparse.ArgumentParser(
        description="Sincroniza map_data/ con archives/map_data.xz",
    )
    parser.add_argument("--archive", default=str(DEFAULT_ARCHIVE))
    parser.add_argument("--map-data", default=str(DEFAULT_MAP_DATA))

    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("status")

    pull_parser = subparsers.add_parser("pull")
    pull_parser.add_argument("--force", "-f", action="store_true")

    push_parser = subparsers.add_parser("push")
    push_parser.add_argument("--force", "-f", action="store_true")
    push_parser.add_argument("--level", type=int, default=9)

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    if args.command == "status":
        sys.exit(cmd_status(args))
    elif args.command == "pull":
        sys.exit(cmd_pull(args))
    elif args.command == "push":
        sys.exit(cmd_push(args))


if __name__ == "__main__":
    main()
