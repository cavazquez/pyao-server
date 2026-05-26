"""Carga NDJSON de un solo mapa (rangos blocked_1-50.json, etc.)."""

from __future__ import annotations

import logging
from pathlib import Path

from src.services.map.ndjson_reader import iter_ndjson_entries

logger = logging.getLogger(__name__)


def find_file_for_map(maps_dir: Path, pattern: str, map_id: int) -> Path | None:
    """Encuentra el archivo cuyo rango de mapas incluye ``map_id``."""
    for file_path in maps_dir.glob(pattern):
        try:
            stem = file_path.stem
            range_part = stem.split("_")[1]
            start_map = int(range_part.split("-")[0])
            end_map = int(range_part.split("-")[1])

            if start_map <= map_id <= end_map:
                return file_path
        except ValueError, IndexError:
            continue
    return None


def parse_blocked_for_map(
    blocked_path: Path | None, map_id: int
) -> tuple[
    set[tuple[int, int]],
    set[tuple[int, int]],
    set[tuple[int, int]],
    set[tuple[int, int]],
]:
    """Procesa un archivo blocked para un único map_id."""
    blocked: set[tuple[int, int]] = set()
    water: set[tuple[int, int]] = set()
    trees: set[tuple[int, int]] = set()
    mines: set[tuple[int, int]] = set()

    if not blocked_path or not blocked_path.exists():
        return blocked, water, trees, mines

    for _line_number, entry in iter_ndjson_entries(blocked_path, log=logger):
        if entry.get("m") != map_id:
            continue

        tile_type = entry.get("t")
        x = entry.get("x")
        y = entry.get("y")

        if not isinstance(x, int) or not isinstance(y, int):
            continue

        if tile_type == "b":
            blocked.add((x, y))
        elif tile_type == "w":
            water.add((x, y))
            blocked.add((x, y))
        elif tile_type == "t":
            trees.add((x, y))
            blocked.add((x, y))
        elif tile_type == "m":
            mines.add((x, y))
            blocked.add((x, y))

    return blocked, water, trees, mines


def parse_objects_for_map(
    objects_path: Path | None,
    map_id: int,
    trees: set[tuple[int, int]],
    mines: set[tuple[int, int]],
    blocked: set[tuple[int, int]],
    water: set[tuple[int, int]],
    anvils: set[tuple[int, int]],
    forges: set[tuple[int, int]],
) -> None:
    """Procesa objects NDJSON para un único map_id."""
    if not objects_path or not objects_path.exists():
        return

    for _line_number, entry in iter_ndjson_entries(objects_path, log=logger):
        if entry.get("m") != map_id:
            continue

        tile_type = entry.get("t")
        x = entry.get("x")
        y = entry.get("y")

        if not isinstance(x, int) or not isinstance(y, int):
            continue

        if tile_type == "tree":
            trees.add((x, y))
            blocked.add((x, y))
        elif tile_type == "mine":
            mines.add((x, y))
            blocked.add((x, y))
        elif tile_type == "anvil":
            anvils.add((x, y))
            blocked.add((x, y))
        elif tile_type == "forge":
            forges.add((x, y))
            blocked.add((x, y))
        elif tile_type == "water":
            water.add((x, y))
        elif tile_type == "sign":
            pass


def load_signs_from_objects(objects_path: Path | None, map_id: int) -> dict[tuple[int, int], int]:
    """Carteles desde objects NDJSON para un mapa."""
    signs_dict: dict[tuple[int, int], int] = {}

    if not objects_path or not objects_path.exists():
        return signs_dict

    for _line_number, entry in iter_ndjson_entries(objects_path, log=logger):
        if entry.get("m") != map_id:
            continue

        if entry.get("t") != "sign":
            continue

        x = entry.get("x")
        y = entry.get("y")
        grh = entry.get("g")

        if isinstance(x, int) and isinstance(y, int) and isinstance(grh, int):
            signs_dict[x, y] = grh

    return signs_dict


def load_doors_from_objects(objects_path: Path | None, map_id: int) -> dict[tuple[int, int], int]:
    """Puertas desde objects NDJSON para un mapa."""
    doors_dict: dict[tuple[int, int], int] = {}

    if not objects_path or not objects_path.exists():
        return doors_dict

    for _line_number, entry in iter_ndjson_entries(objects_path, log=logger):
        if entry.get("m") != map_id:
            continue

        if entry.get("t") != "door":
            continue

        x = entry.get("x")
        y = entry.get("y")
        grh = entry.get("g")

        if isinstance(x, int) and isinstance(y, int) and isinstance(grh, int):
            doors_dict[x, y] = grh

    return doors_dict


def load_single_map_into(
    resources: dict[str, dict[str, set[tuple[int, int]]]],
    signs: dict[str, dict[tuple[int, int], int]],
    doors: dict[str, dict[tuple[int, int], int]],
    maps_dir: Path,
    map_id: int,
    *,
    log: logging.Logger,
) -> None:
    """Carga un mapa en los dicts destino."""
    map_key = f"map_{map_id}"

    blocked_path = find_file_for_map(maps_dir, "blocked_*.json", map_id)
    objects_path = find_file_for_map(maps_dir, "objects_*.json", map_id)

    if blocked_path is None and objects_path is None:
        log.debug("No se encontraron archivos de datos para mapa %d", map_id)
        return

    try:
        blocked, water, trees, mines = parse_blocked_for_map(blocked_path, map_id)

        anvils: set[tuple[int, int]] = set()
        forges: set[tuple[int, int]] = set()

        parse_objects_for_map(
            objects_path,
            map_id,
            trees,
            mines,
            blocked,
            water,
            anvils,
            forges,
        )

        if blocked_path and objects_path:
            blocked_name = blocked_path.name if blocked_path else "(sin blocked)"
            source = f"{blocked_name} + {objects_path.name}"
        else:
            source = (
                blocked_path.name
                if blocked_path
                else (objects_path.name if objects_path else "unknown")
            )

        resources[map_key] = {
            "blocked": blocked,
            "water": water,
            "trees": trees,
            "mines": mines,
            "anvils": anvils,
            "forges": forges,
        }

        signs_dict = load_signs_from_objects(objects_path, map_id)
        if signs_dict:
            signs[map_key] = signs_dict

        doors_dict = load_doors_from_objects(objects_path, map_id)
        if doors_dict:
            doors[map_key] = doors_dict

        log.info(
            "  %s (%s): %d bloqueados, %d agua, %d árboles, %d minas, %d yunques, %d fraguas",
            map_key,
            source,
            len(blocked),
            len(water),
            len(trees),
            len(mines),
            len(anvils),
            len(forges),
        )

    except Exception:
        log.exception("Error cargando datos de recursos para mapa %d", map_id)
