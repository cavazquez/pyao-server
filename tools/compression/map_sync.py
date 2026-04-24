"""Herramienta para sincronizar map_data con archives/map_data.xz.

Comandos:
    status  - Muestra el estado de sincronización
    pull    - Descomprime archives/map_data.xz a map_data/
    push    - Comprime map_data/ a archives/map_data.xz
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
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
    """Retorna la ruta del archivo de metadatos de sincronización.

    Returns:
        Path al archivo de metadatos.
    """
    return map_data_dir / SYNC_METADATA_FILE


def read_sync_metadata(map_data_dir: Path) -> dict:
    """Lee los metadatos de sincronización.

    Returns:
        Diccionario con metadatos o dict vacío si no existe.
    """
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
    """Encuentra el archivo más recientemente modificado en un directorio.

    Returns:
        Tupla (path, mtime) del archivo más nuevo, o (None, 0) si no hay archivos.
    """
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
    """Determina el estado de sincronización entre map_data y archive.

    Returns:
        SyncInfo con el estado actual.
    """
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
            "⚠️  CONFLICTO: Hay cambios locales Y el archive fue actualizado.\n"
            "   Opciones:\n"
            "   - 'map_sync push' para guardar tus cambios\n"
            "   - 'map_sync pull --force' para descartar cambios locales"
        )
    elif has_local_changes:
        info.status = SyncStatus.LOCAL_CHANGES
        info.message = (
            "📝 Hay cambios locales no comprimidos.\n"
            f"   Archivo más reciente: {info.newest_local_file}\n"
            "   Ejecuta 'map_sync push' para guardar los cambios."
        )
    elif archive_is_newer:
        info.status = SyncStatus.ARCHIVE_NEWER
        info.message = (
            "📥 El archive es más nuevo (posible git pull).\n"
            "   Ejecuta 'map_sync pull' para actualizar map_data/."
        )
    else:
        info.status = SyncStatus.IN_SYNC
        info.message = "✅ Sincronizado."

    return info


def format_timestamp(ts: float | None) -> str:
    """Formatea un timestamp Unix a string legible.

    Returns:
        String formateado o 'N/A' si es None.
    """
    if ts is None or ts == 0:
        return "N/A"
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def cmd_status(args: argparse.Namespace) -> int:
    """Comando: muestra el estado de sincronización.

    Returns:
        0 si está sincronizado, 1 si no.
    """
    archive_path = Path(args.archive)
    map_data_dir = Path(args.map_data)

    info = get_sync_status(archive_path, map_data_dir)

    print("\n" + "=" * 60)
    print("  Estado de Sincronización de Mapas")
    print("=" * 60)
    print(f"  Archive:        {archive_path}")
    print(f"  Map Data:       {map_data_dir}")
    print("-" * 60)
    print(f"  Archive mtime:       {format_timestamp(info.archive_mtime)}")
    print(f"  Última descompresión: {format_timestamp(info.last_decompress)}")
    print(f"  Archivo local más nuevo: {info.newest_local_file or 'N/A'}")
    print(f"  mtime más nuevo:     {format_timestamp(info.newest_local_mtime)}")
    print("-" * 60)
    print(f"\n{info.message}\n")

    return 0 if info.status == SyncStatus.IN_SYNC else 1


def cmd_pull(args: argparse.Namespace) -> int:
    """Comando: descomprime archive a map_data/.

    Returns:
        0 si éxito, 1 si error.
    """
    archive_path = Path(args.archive)
    map_data_dir = Path(args.map_data)

    if not archive_path.exists():
        print(f"❌ Error: No existe {archive_path}")
        return 1

    info = get_sync_status(archive_path, map_data_dir)

    if info.status in {SyncStatus.LOCAL_CHANGES, SyncStatus.CONFLICT}:
        if not args.force:
            print("\n⚠️  Hay cambios locales que se perderán:")
            print(f"   Archivo más reciente: {info.newest_local_file}")
            print(f"   Modificado: {format_timestamp(info.newest_local_mtime)}")
            print("\n   Usa --force para sobrescribir, o 'map_sync push' primero.\n")
            return 1
        print("⚠️  Sobrescribiendo cambios locales (--force)")

    print(f"📥 Descomprimiendo {archive_path} → {map_data_dir}...")

    try:
        decompress_map_data(archive_path, map_data_dir, overwrite=True)
        write_sync_metadata(map_data_dir, {
            "last_decompress": time.time(),
            "archive_mtime": archive_path.stat().st_mtime,
        })
        print("✅ Descompresión completada. map_data/ actualizado.")
    except (OSError, ValueError) as e:
        print(f"❌ Error durante descompresión: {e}")
        return 1
    else:
        return 0


def cmd_push(args: argparse.Namespace) -> int:
    """Comando: comprime map_data/ a archive.

    Returns:
        0 si éxito, 1 si error.
    """
    archive_path = Path(args.archive)
    map_data_dir = Path(args.map_data)

    if not map_data_dir.exists():
        print(f"❌ Error: No existe {map_data_dir}")
        return 1

    info = get_sync_status(archive_path, map_data_dir)

    if info.status == SyncStatus.IN_SYNC and not args.force:
        print("✅ Sincronizado. Nada que comprimir.")
        print("   Usa --force para forzar la compresión.")
        return 0

    print(f"📤 Comprimiendo {map_data_dir} → {archive_path}...")

    try:
        compress_map_data(map_data_dir, archive_path, level=args.level)
        write_sync_metadata(map_data_dir, {
            "last_decompress": time.time(),
            "archive_mtime": archive_path.stat().st_mtime,
        })
        print("✅ Compresión completada. Archive actualizado.")
    except (OSError, ValueError) as e:
        print(f"❌ Error durante compresión: {e}")
        return 1
    else:
        return 0


def check_map_sync_on_startup(
    archive_path: Path = DEFAULT_ARCHIVE,
    map_data_dir: Path = DEFAULT_MAP_DATA,
    auto_decompress: bool = True,
) -> bool:
    """Verifica sincronización al iniciar el servidor.

    Args:
        archive_path: Ruta al archivo comprimido.
        map_data_dir: Directorio de datos de mapas.
        auto_decompress: Si True, descomprime automáticamente cuando es seguro.

    Returns:
        True si map_data/ está listo para usar, False si hay problemas.
    """
    info = get_sync_status(archive_path, map_data_dir)

    if info.status == SyncStatus.NO_MAP_DATA:
        if auto_decompress:
            logger.info("map_data/ no existe. Descomprimiendo desde archive...")
            try:
                decompress_map_data(archive_path, map_data_dir, overwrite=False)
                write_sync_metadata(map_data_dir, {
                    "last_decompress": time.time(),
                    "archive_mtime": archive_path.stat().st_mtime,
                })
                logger.info("✓ map_data/ creado desde archive")
            except (OSError, ValueError):
                logger.exception("Error descomprimiendo map_data")
                return False
            else:
                return True
        else:
            logger.warning(
                "map_data/ no existe. En desarrollo: "
                "uv run python -m tools.compression.map_sync pull"
            )
            return False

    if info.status == SyncStatus.NO_ARCHIVE:
        logger.debug(
            "archives/map_data.xz no existe (normal en instalaciones sin archivos comprimidos)."
        )
        return map_data_dir.exists()

    if info.status == SyncStatus.LOCAL_CHANGES:
        logger.warning(
            "⚠️  Hay cambios locales en map_data/ no comprimidos. "
            "En desarrollo: uv run python -m tools.compression.map_sync push"
        )
        return True

    if info.status == SyncStatus.ARCHIVE_NEWER:
        logger.warning(
            "⚠️  archives/map_data.xz es más nuevo que map_data/. "
            "En desarrollo: uv run python -m tools.compression.map_sync pull"
        )
        return True

    if info.status == SyncStatus.CONFLICT:
        logger.warning(
            "⚠️  CONFLICTO: Hay cambios locales Y archive actualizado. "
            "En desarrollo: uv run python -m tools.compression.map_sync status"
        )
        return True

    return True


def main() -> None:
    """Punto de entrada CLI."""
    parser = argparse.ArgumentParser(
        description="Sincroniza map_data/ con archives/map_data.xz",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  uv run python -m tools.compression.map_sync status
  uv run python -m tools.compression.map_sync pull
  uv run python -m tools.compression.map_sync pull --force
  uv run python -m tools.compression.map_sync push
  uv run python -m tools.compression.map_sync push --level 6
""",
    )

    parser.add_argument(
        "--archive",
        type=str,
        default=str(DEFAULT_ARCHIVE),
        help="Ruta al archivo comprimido (default: archives/map_data.xz)",
    )
    parser.add_argument(
        "--map-data",
        type=str,
        default=str(DEFAULT_MAP_DATA),
        help="Directorio de datos de mapas (default: map_data)",
    )

    subparsers = parser.add_subparsers(dest="command", help="Comandos disponibles")

    subparsers.add_parser("status", help="Muestra el estado de sincronización")

    pull_parser = subparsers.add_parser("pull", help="Descomprime archive a map_data/")
    pull_parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="Sobrescribe cambios locales sin preguntar",
    )

    push_parser = subparsers.add_parser("push", help="Comprime map_data/ a archive")
    push_parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="Fuerza compresión aunque esté sincronizado",
    )
    push_parser.add_argument(
        "--level",
        type=int,
        default=9,
        help="Nivel de compresión LZMA (0-9, default: 9)",
    )

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
