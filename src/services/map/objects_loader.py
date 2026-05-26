"""Carga de archivos objects_*.json agrupando recursos por mapa."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from src.services.map.ndjson_reader import iter_ndjson_entries

logger = logging.getLogger(__name__)

_KNOWN_TILE_TYPES = frozenset({"tree", "mine", "anvil", "forge", "water", "sign", "door"})


def process_objects_file(
    objects_path: Path,
    trees_by_map: dict[int, set[tuple[int, int]]],
    mines_by_map: dict[int, set[tuple[int, int]]],
    blocked_by_map: dict[int, set[tuple[int, int]]],
    signs_by_map: dict[int, dict[tuple[int, int], int]],
    doors_by_map: dict[int, dict[tuple[int, int], int]],
    water_by_map: dict[int, set[tuple[int, int]]],
    anvils_by_map: dict[int, set[tuple[int, int]]],
    forges_by_map: dict[int, set[tuple[int, int]]],
    *,
    generic_objects_by_map: dict[int, list[dict[str, Any]]] | None = None,
) -> None:
    """Procesa un archivo objects_*.json y acumula por map_id."""
    if not objects_path.exists():
        return

    for _line_number, entry in iter_ndjson_entries(objects_path, log=logger):
        map_id = entry.get("m")
        if not isinstance(map_id, int):
            continue

        tile_type = entry.get("t")
        x = entry.get("x")
        y = entry.get("y")

        if not isinstance(x, int) or not isinstance(y, int):
            continue

        if tile_type == "tree":
            trees_by_map.setdefault(map_id, set()).add((x, y))
            blocked_by_map.setdefault(map_id, set()).add((x, y))
        elif tile_type == "mine":
            mines_by_map.setdefault(map_id, set()).add((x, y))
            blocked_by_map.setdefault(map_id, set()).add((x, y))
        elif tile_type == "anvil":
            anvils_by_map.setdefault(map_id, set()).add((x, y))
            blocked_by_map.setdefault(map_id, set()).add((x, y))
        elif tile_type == "forge":
            forges_by_map.setdefault(map_id, set()).add((x, y))
            blocked_by_map.setdefault(map_id, set()).add((x, y))
        elif tile_type == "water":
            water_by_map.setdefault(map_id, set()).add((x, y))
        elif tile_type == "sign":
            grh = entry.get("g")
            if isinstance(grh, int):
                signs_by_map.setdefault(map_id, {})[x, y] = grh
        elif tile_type == "door":
            grh = entry.get("g")
            if isinstance(grh, int):
                doors_by_map.setdefault(map_id, {})[x, y] = grh
        elif generic_objects_by_map is not None and tile_type not in _KNOWN_TILE_TYPES:
            generic_objects_by_map.setdefault(map_id, []).append(entry)
