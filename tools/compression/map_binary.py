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
from datetime import UTC, datetime
from pathlib import Path

import msgpack

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

    # Estructuras para acumular datos
    all_blocked: dict[int, list[tuple[int, int]]] = {}
    all_water: dict[int, list[tuple[int, int]]] = {}
    all_trees: dict[int, list[tuple[int, int]]] = {}
    all_mines: dict[int, list[tuple[int, int]]] = {}
    all_anvils: dict[int, list[tuple[int, int]]] = {}
    all_forges: dict[int, list[tuple[int, int]]] = {}
    all_signs: dict[int, list[tuple[int, int, int]]] = {}  # (x, y, grh)
    all_doors: dict[int, list[tuple[int, int, int]]] = {}  # (x, y, grh)
    all_objects: dict[int, list[dict]] = {}
    all_transitions: dict[int, list[dict]] = {}

    # Procesar archivos blocked_*.json
    blocked_files = sorted(map_data_dir.glob("blocked_*.json"))
    for blocked_path in blocked_files:
        logger.info("Procesando %s...", blocked_path.name)
        _process_blocked_file(
            blocked_path, all_blocked, all_water, all_trees, all_mines
        )

    # Procesar archivos objects_*.json
    objects_files = sorted(map_data_dir.glob("objects_*.json"))
    for objects_path in objects_files:
        logger.info("Procesando %s...", objects_path.name)
        _process_objects_file(
            objects_path, all_trees, all_mines, all_blocked,
            all_signs, all_doors, all_water, all_anvils, all_forges, all_objects
        )

    # Procesar archivos transitions_*.json
    transitions_files = sorted(map_data_dir.glob("transitions_*.json"))
    for transitions_path in transitions_files:
        logger.info("Procesando %s...", transitions_path.name)
        _process_transitions_file(transitions_path, all_transitions)

    # Construir payload binario
    payload = {
        "version": BINARY_VERSION,
        "blocked": {str(k): list(v) for k, v in all_blocked.items()},
        "water": {str(k): list(v) for k, v in all_water.items()},
        "trees": {str(k): list(v) for k, v in all_trees.items()},
        "mines": {str(k): list(v) for k, v in all_mines.items()},
        "anvils": {str(k): list(v) for k, v in all_anvils.items()},
        "forges": {str(k): list(v) for k, v in all_forges.items()},
        "signs": {str(k): v for k, v in all_signs.items()},
        "doors": {str(k): v for k, v in all_doors.items()},
        "objects": {str(k): v for k, v in all_objects.items()},
        "transitions": {str(k): v for k, v in all_transitions.items()},
    }

    # Guardar como MessagePack
    output_file = map_binary_dir / "maps.msgpack"
    with output_file.open("wb") as f:
        msgpack.pack(payload, f, use_bin_type=True)

    # Guardar metadata
    metadata = {
        "version": BINARY_VERSION,
        "created_at": time.time(),
        "source_dir": str(map_data_dir),
        "map_count": len(set(all_blocked.keys()) | set(all_water.keys())),
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


def _process_blocked_file(
    blocked_path: Path,
    all_blocked: dict[int, list[tuple[int, int]]],
    all_water: dict[int, list[tuple[int, int]]],
    all_trees: dict[int, list[tuple[int, int]]],
    all_mines: dict[int, list[tuple[int, int]]],
) -> None:
    """Procesa un archivo blocked_*.json."""
    with blocked_path.open(encoding="utf-8") as f:
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

            tile_type = entry.get("t")
            x = entry.get("x")
            y = entry.get("y")

            if not isinstance(x, int) or not isinstance(y, int):
                continue

            if map_id not in all_blocked:
                all_blocked[map_id] = []

            coord = (x, y)

            if tile_type == "b":
                all_blocked[map_id].append(coord)
            elif tile_type == "w":
                if map_id not in all_water:
                    all_water[map_id] = []
                all_water[map_id].append(coord)
                all_blocked[map_id].append(coord)
            elif tile_type == "t":
                if map_id not in all_trees:
                    all_trees[map_id] = []
                all_trees[map_id].append(coord)
                all_blocked[map_id].append(coord)
            elif tile_type == "m":
                if map_id not in all_mines:
                    all_mines[map_id] = []
                all_mines[map_id].append(coord)
                all_blocked[map_id].append(coord)


def _process_objects_file(  # noqa: PLR0915
    objects_path: Path,
    all_trees: dict[int, list[tuple[int, int]]],
    all_mines: dict[int, list[tuple[int, int]]],
    all_blocked: dict[int, list[tuple[int, int]]],
    all_signs: dict[int, list[tuple[int, int, int]]],
    all_doors: dict[int, list[tuple[int, int, int]]],
    all_water: dict[int, list[tuple[int, int]]],
    all_anvils: dict[int, list[tuple[int, int]]],
    all_forges: dict[int, list[tuple[int, int]]],
    all_objects: dict[int, list[dict]],
) -> None:
    """Procesa un archivo objects_*.json."""
    with objects_path.open(encoding="utf-8") as f:
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

            tile_type = entry.get("t")
            x = entry.get("x")
            y = entry.get("y")

            if not isinstance(x, int) or not isinstance(y, int):
                continue

            coord = (x, y)

            # Inicializar listas si no existen
            if map_id not in all_blocked:
                all_blocked[map_id] = []

            if tile_type == "tree":
                if map_id not in all_trees:
                    all_trees[map_id] = []
                all_trees[map_id].append(coord)
                all_blocked[map_id].append(coord)
            elif tile_type == "mine":
                if map_id not in all_mines:
                    all_mines[map_id] = []
                all_mines[map_id].append(coord)
                all_blocked[map_id].append(coord)
            elif tile_type == "anvil":
                if map_id not in all_anvils:
                    all_anvils[map_id] = []
                all_anvils[map_id].append(coord)
                all_blocked[map_id].append(coord)
            elif tile_type == "forge":
                if map_id not in all_forges:
                    all_forges[map_id] = []
                all_forges[map_id].append(coord)
                all_blocked[map_id].append(coord)
            elif tile_type == "water":
                if map_id not in all_water:
                    all_water[map_id] = []
                all_water[map_id].append(coord)
            elif tile_type == "sign":
                grh = entry.get("g")
                if isinstance(grh, int):
                    if map_id not in all_signs:
                        all_signs[map_id] = []
                    all_signs[map_id].append((x, y, grh))
            elif tile_type == "door":
                grh = entry.get("g")
                if isinstance(grh, int):
                    if map_id not in all_doors:
                        all_doors[map_id] = []
                    all_doors[map_id].append((x, y, grh))
            else:
                # Guardar objetos genéricos
                if map_id not in all_objects:
                    all_objects[map_id] = []
                all_objects[map_id].append(entry)


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

    # Verificar si algún archivo JSON es más nuevo
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

    # Mostrar info
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
