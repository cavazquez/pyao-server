"""Carga de archivos objects_*.json agrupando recursos por mapa."""

from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


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
) -> None:
    """Procesa un archivo objects_*.json y acumula por map_id."""
    if not objects_path.exists():
        return

    with objects_path.open(encoding="utf-8") as f:
        for line_number, raw_line in enumerate(f, start=1):
            line = raw_line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                logger.debug(
                    "Entrada inválida en %s línea %d: %s",
                    objects_path.name,
                    line_number,
                    line,
                )
                continue

            if not isinstance(entry, dict):
                continue

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
