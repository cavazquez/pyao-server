"""Herramienta para convertir map_data (JSON) a formato binario (MessagePack).

El formato binario es ~10x más rápido de cargar que JSON.
"""
# ruff: noqa: DOC201

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

import msgpack

from src.services.map.blocked_loader import process_blocked_file
from src.services.map.objects_loader import process_objects_file

logger = logging.getLogger(__name__)

DEFAULT_MAP_DATA = Path("map_data")
DEFAULT_MAP_BINARY = Path("map_binary")
BINARY_VERSION = 1


def convert_json_to_binary(  # noqa: PLR0914
    map_data_dir: Path = DEFAULT_MAP_DATA,
    map_binary_dir: Path = DEFAULT_MAP_BINARY,
) -> bool:
    """Convierte archivos JSON de map_data a formato binario MessagePack.

    Returns:
        True si la conversión fue exitosa.
    """
    if not map_data_dir.exists():
        logger.error("map_data/ no existe: %s", map_data_dir)
        return False

    map_binary_dir.mkdir(parents=True, exist_ok=True)
    start_time = time.time()

    blocked_by_map: dict[int, set[tuple[int, int]]] = defaultdict(set)
    water_by_map: dict[int, set[tuple[int, int]]] = defaultdict(set)
    trees_by_map: dict[int, set[tuple[int, int]]] = defaultdict(set)
    mines_by_map: dict[int, set[tuple[int, int]]] = defaultdict(set)
    anvils_by_map: dict[int, set[tuple[int, int]]] = defaultdict(set)
    forges_by_map: dict[int, set[tuple[int, int]]] = defaultdict(set)
    signs_by_map: dict[int, dict[tuple[int, int], int]] = {}
    doors_by_map: dict[int, dict[tuple[int, int], int]] = {}
    generic_objects_by_map: dict[int, list[dict]] = {}
    all_transitions: dict[int, list[dict]] = {}

    blocked_files = sorted(map_data_dir.glob("blocked_*.json"))
    for blocked_path in blocked_files:
        logger.info("Procesando %s...", blocked_path.name)
        process_blocked_file(
            blocked_path,
            blocked_by_map,
            water_by_map,
            trees_by_map,
            mines_by_map,
        )

    objects_files = sorted(map_data_dir.glob("objects_*.json"))
    for objects_path in objects_files:
        logger.info("Procesando %s...", objects_path.name)
        process_objects_file(
            objects_path,
            trees_by_map,
            mines_by_map,
            blocked_by_map,
            signs_by_map,
            doors_by_map,
            water_by_map,
            anvils_by_map,
            forges_by_map,
            generic_objects_by_map=generic_objects_by_map,
        )

    transitions_files = sorted(map_data_dir.glob("transitions_*.json"))
    for transitions_path in transitions_files:
        logger.info("Procesando %s...", transitions_path.name)
        _process_transitions_file(transitions_path, all_transitions)

    payload = {
        "version": BINARY_VERSION,
        "blocked": {str(k): list(v) for k, v in blocked_by_map.items()},
        "water": {str(k): list(v) for k, v in water_by_map.items()},
        "trees": {str(k): list(v) for k, v in trees_by_map.items()},
        "mines": {str(k): list(v) for k, v in mines_by_map.items()},
        "anvils": {str(k): list(v) for k, v in anvils_by_map.items()},
        "forges": {str(k): list(v) for k, v in forges_by_map.items()},
        "signs": {
            str(map_id): [[x, y, grh] for (x, y), grh in signs.items()]
            for map_id, signs in signs_by_map.items()
        },
        "doors": {
            str(map_id): [[x, y, grh] for (x, y), grh in doors.items()]
            for map_id, doors in doors_by_map.items()
        },
        "objects": {str(k): v for k, v in generic_objects_by_map.items()},
        "transitions": {str(k): v for k, v in all_transitions.items()},
    }

    output_file = map_binary_dir / "maps.msgpack"
    with output_file.open("wb") as f:
        msgpack.pack(payload, f, use_bin_type=True)

    metadata = {
        "version": BINARY_VERSION,
        "created_at": time.time(),
        "source_dir": str(map_data_dir),
        "map_count": len(set(blocked_by_map.keys()) | set(water_by_map.keys())),
    }
    metadata_file = map_binary_dir / "metadata.json"
    with metadata_file.open("w") as f:
        json.dump(metadata, f, indent=2)

    elapsed = time.time() - start_time
    file_size = output_file.stat().st_size / 1024 / 1024

    logger.info(
        "Conversion completada en %.2fs: %s (%.2f MB)",
        elapsed, output_file, file_size
    )
    return True


def _process_transitions_file(
    transitions_path: Path,
    all_transitions: dict[int, list[dict]],
) -> None:
    """Procesa un archivo transitions_*.json."""
    with transitions_path.open(encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            map_id = entry.get("m")
            if not isinstance(map_id, int):
                continue

            if map_id not in all_transitions:
                all_transitions[map_id] = []
            all_transitions[map_id].append(entry)


def load_binary_maps(map_binary_dir: Path = DEFAULT_MAP_BINARY) -> dict | None:
    """Carga datos de mapas desde formato binario.

    Returns:
        Diccionario con datos de mapas o None si no existe.
    """
    binary_file = map_binary_dir / "maps.msgpack"
    if not binary_file.exists():
        return None

    start_time = time.time()
    with binary_file.open("rb") as f:
        data = msgpack.unpack(f, raw=False)

    elapsed = time.time() - start_time
    logger.info("Mapas binarios cargados en %.3fs desde %s", elapsed, binary_file)
    return data


def check_binary_needs_rebuild(
    map_data_dir: Path = DEFAULT_MAP_DATA,
    map_binary_dir: Path = DEFAULT_MAP_BINARY,
) -> bool:
    """Verifica si map_binary necesita ser regenerado.

    Returns:
        True si necesita rebuild, False si está actualizado.
    """
    metadata_file = map_binary_dir / "metadata.json"
    if not metadata_file.exists():
        return True

    try:
        with metadata_file.open() as f:
            metadata = json.load(f)
    except (json.JSONDecodeError, OSError):
        return True

    binary_created = metadata.get("created_at", 0)

    for pattern in ["blocked_*.json", "objects_*.json", "transitions_*.json"]:
        for json_file in map_data_dir.glob(pattern):
            if json_file.stat().st_mtime > binary_created:
                return True

    return False


def ensure_binary_maps(
    map_data_dir: Path = DEFAULT_MAP_DATA,
    map_binary_dir: Path = DEFAULT_MAP_BINARY,
    force: bool = False,
) -> bool:
    """Asegura que map_binary exista y esté actualizado.

    Returns:
        True si map_binary está listo para usar.
    """
    if not force and not check_binary_needs_rebuild(map_data_dir, map_binary_dir):
        logger.debug("map_binary/ está actualizado")
        return True

    if not map_data_dir.exists():
        logger.warning("map_data/ no existe, no se puede generar map_binary/")
        return False

    logger.info("Regenerando map_binary/ desde map_data/...")
    return convert_json_to_binary(map_data_dir, map_binary_dir)


def cmd_convert(args: argparse.Namespace) -> int:
    """Comando: convierte map_data a map_binary."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    map_data_dir = Path(args.map_data)
    map_binary_dir = Path(args.map_binary)

    if not map_data_dir.exists():
        print(f"Error: No existe {map_data_dir}")
        return 1

    print(f"Convirtiendo {map_data_dir} -> {map_binary_dir}...")

    if convert_json_to_binary(map_data_dir, map_binary_dir):
        print("Conversion completada.")
        return 0
    print("Error durante conversion.")
    return 1


def cmd_status(args: argparse.Namespace) -> int:
    """Comando: muestra estado de map_binary."""
    map_data_dir = Path(args.map_data)
    map_binary_dir = Path(args.map_binary)

    print("\n" + "=" * 50)
    print("  Estado de Mapas Binarios")
    print("=" * 50)

    binary_file = map_binary_dir / "maps.msgpack"
    metadata_file = map_binary_dir / "metadata.json"

    if not binary_file.exists():
        print("  map_binary/: NO EXISTE")
        print("\n  Ejecuta: uv run python -m tools.compression.map_binary convert\n")
        return 1

    size_mb = binary_file.stat().st_size / 1024 / 1024
    print(f"  Archivo: {binary_file}")
    print(f"  Tamano:  {size_mb:.2f} MB")

    if metadata_file.exists():
        with metadata_file.open() as f:
            metadata = json.load(f)
        created = datetime.fromtimestamp(
            metadata.get("created_at", 0), tz=UTC
        ).strftime("%Y-%m-%d %H:%M:%S")
        print(f"  Creado:  {created}")
        print(f"  Mapas:   {metadata.get('map_count', '?')}")

    needs_rebuild = check_binary_needs_rebuild(map_data_dir, map_binary_dir)
    print(f"\n  Estado:  {'DESACTUALIZADO' if needs_rebuild else 'Actualizado'}")

    if needs_rebuild:
        print("\n  Ejecuta: uv run python -m tools.compression.map_binary convert\n")
        return 1

    print()
    return 0


def main() -> None:
    """Punto de entrada CLI."""
    parser = argparse.ArgumentParser(
        description="Convierte map_data (JSON) a formato binario (MessagePack)",
    )
    parser.add_argument("--map-data", default=str(DEFAULT_MAP_DATA))
    parser.add_argument("--map-binary", default=str(DEFAULT_MAP_BINARY))

    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("convert", help="Convierte JSON a binario")
    subparsers.add_parser("status", help="Muestra estado")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    if args.command == "convert":
        sys.exit(cmd_convert(args))
    elif args.command == "status":
        sys.exit(cmd_status(args))


if __name__ == "__main__":
    main()
