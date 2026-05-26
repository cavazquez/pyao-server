"""Carga de archivos blocked_*.json agrupando recursos por mapa."""

from __future__ import annotations

import logging
from pathlib import Path

from src.services.map.ndjson_reader import iter_ndjson_entries

logger = logging.getLogger(__name__)


def process_blocked_file(
    blocked_path: Path,
    blocked_by_map: dict[int, set[tuple[int, int]]],
    water_by_map: dict[int, set[tuple[int, int]]],
    trees_by_map: dict[int, set[tuple[int, int]]],
    mines_by_map: dict[int, set[tuple[int, int]]],
) -> None:
    """Procesa un archivo blocked_*.json y acumula por map_id."""
    if not blocked_path.exists():
        return

    for _line_number, entry in iter_ndjson_entries(blocked_path, log=logger):
        map_id = entry.get("m")
        if not isinstance(map_id, int):
            continue

        tile_type = entry.get("t")
        x = entry.get("x")
        y = entry.get("y")

        if not isinstance(x, int) or not isinstance(y, int):
            continue

        if tile_type == "b":  # blocked
            blocked_by_map.setdefault(map_id, set()).add((x, y))
        elif tile_type == "w":  # water
            water_by_map.setdefault(map_id, set()).add((x, y))
            blocked_by_map.setdefault(map_id, set()).add((x, y))
        elif tile_type == "t":  # tree
            trees_by_map.setdefault(map_id, set()).add((x, y))
            blocked_by_map.setdefault(map_id, set()).add((x, y))
        elif tile_type == "m":  # mine
            mines_by_map.setdefault(map_id, set()).add((x, y))
            blocked_by_map.setdefault(map_id, set()).add((x, y))
