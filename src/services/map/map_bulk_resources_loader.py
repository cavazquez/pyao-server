"""Carga masiva de recursos desde todos los ``blocked_*.json`` / ``objects_*.json``."""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from pathlib import Path

from src.services.map.blocked_loader import process_blocked_file
from src.services.map.objects_loader import process_objects_file


def gather_map_files(
    maps_dir: Path, log: logging.Logger
) -> tuple[list[Path] | None, list[Path] | None]:
    if not maps_dir.exists():
        log.warning("Directorio de mapas no encontrado: %s", maps_dir)
        maps_dir.mkdir(parents=True, exist_ok=True)
        return None, None

    blocked_files = sorted(maps_dir.glob("blocked_*.json"))
    objects_files = sorted(maps_dir.glob("objects_*.json"))
    if not blocked_files and not objects_files:
        log.warning("No se encontraron archivos de mapas en %s", maps_dir)
        return None, None
    return blocked_files, objects_files


def load_map_resources(
    blocked_files: list[Path],
    objects_files: list[Path],
) -> tuple[
    dict[int, set[tuple[int, int]]],
    dict[int, set[tuple[int, int]]],
    dict[int, set[tuple[int, int]]],
    dict[int, set[tuple[int, int]]],
    dict[int, set[tuple[int, int]]],
    dict[int, set[tuple[int, int]]],
    dict[int, dict[tuple[int, int], int]],
    dict[int, dict[tuple[int, int], int]],
]:
    blocked_by_map: dict[int, set[tuple[int, int]]] = defaultdict(set)
    water_by_map: dict[int, set[tuple[int, int]]] = defaultdict(set)
    trees_by_map: dict[int, set[tuple[int, int]]] = defaultdict(set)
    mines_by_map: dict[int, set[tuple[int, int]]] = defaultdict(set)
    anvils_by_map: dict[int, set[tuple[int, int]]] = defaultdict(set)
    forges_by_map: dict[int, set[tuple[int, int]]] = defaultdict(set)
    signs_by_map: dict[int, dict[tuple[int, int], int]] = {}
    doors_by_map: dict[int, dict[tuple[int, int], int]] = {}

    for blocked_path in blocked_files:
        process_blocked_file(
            blocked_path,
            blocked_by_map,
            water_by_map,
            trees_by_map,
            mines_by_map,
        )

    for objects_path in objects_files:
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
        )

    return (
        blocked_by_map,
        water_by_map,
        trees_by_map,
        mines_by_map,
        anvils_by_map,
        forges_by_map,
        signs_by_map,
        doors_by_map,
    )


def collect_map_ids(
    blocked_by_map: dict[int, set[tuple[int, int]]],
    water_by_map: dict[int, set[tuple[int, int]]],
    trees_by_map: dict[int, set[tuple[int, int]]],
    mines_by_map: dict[int, set[tuple[int, int]]],
    anvils_by_map: dict[int, set[tuple[int, int]]],
    forges_by_map: dict[int, set[tuple[int, int]]],
    signs_by_map: dict[int, dict[tuple[int, int], int]],
    doors_by_map: dict[int, dict[tuple[int, int], int]],
) -> set[int]:
    map_ids: set[int] = set(blocked_by_map.keys())
    map_ids.update(water_by_map.keys())
    map_ids.update(trees_by_map.keys())
    map_ids.update(mines_by_map.keys())
    map_ids.update(anvils_by_map.keys())
    map_ids.update(forges_by_map.keys())
    map_ids.update(signs_by_map.keys())
    map_ids.update(doors_by_map.keys())
    return map_ids


def build_public_structures(
    resources: dict[str, dict[str, set[tuple[int, int]]]],
    signs: dict[str, dict[tuple[int, int], int]],
    doors: dict[str, dict[tuple[int, int], int]],
    map_ids: set[int],
    blocked_by_map: dict[int, set[tuple[int, int]]],
    water_by_map: dict[int, set[tuple[int, int]]],
    trees_by_map: dict[int, set[tuple[int, int]]],
    mines_by_map: dict[int, set[tuple[int, int]]],
    anvils_by_map: dict[int, set[tuple[int, int]]],
    forges_by_map: dict[int, set[tuple[int, int]]],
    signs_by_map: dict[int, dict[tuple[int, int], int]],
    doors_by_map: dict[int, dict[tuple[int, int], int]],
    *,
    log: logging.Logger,
) -> None:
    for map_id in sorted(map_ids):
        map_key = f"map_{map_id}"

        blocked = blocked_by_map.get(map_id, set())
        water = water_by_map.get(map_id, set())
        trees = trees_by_map.get(map_id, set())
        mines = mines_by_map.get(map_id, set())
        anvils = anvils_by_map.get(map_id, set())
        forges = forges_by_map.get(map_id, set())

        resources[map_key] = {
            "blocked": blocked,
            "water": water,
            "trees": trees,
            "mines": mines,
            "anvils": anvils,
            "forges": forges,
        }

        if map_id in signs_by_map:
            signs[map_key] = signs_by_map[map_id]

        if map_id in doors_by_map:
            doors[map_key] = doors_by_map[map_id]

        signs_count = len(signs_by_map.get(map_id, {}))
        doors_count = len(doors_by_map.get(map_id, {}))

        log.info(
            "  %s (multiple files): %d bloqueados, %d agua, %d árboles, %d minas, "
            "%d yunques, %d fraguas, %d carteles, %d puertas",
            map_key,
            len(blocked),
            len(water),
            len(trees),
            len(mines),
            len(anvils),
            len(forges),
            signs_count,
            doors_count,
        )


def run_load_all_maps(
    maps_dir: Path,
    resources: dict[str, dict[str, set[tuple[int, int]]]],
    signs: dict[str, dict[tuple[int, int], int]],
    doors: dict[str, dict[tuple[int, int], int]],
    *,
    log: logging.Logger,
) -> None:
    """Pipeline completo: gather → aggregate → publicar en los dicts del servicio."""
    start_time = time.time()
    try:
        blocked_files, objects_files = gather_map_files(maps_dir, log)
        if blocked_files is None or objects_files is None:
            return

        (
            blocked_by_map,
            water_by_map,
            trees_by_map,
            mines_by_map,
            anvils_by_map,
            forges_by_map,
            signs_by_map,
            doors_by_map,
        ) = load_map_resources(blocked_files, objects_files)

        map_ids = collect_map_ids(
            blocked_by_map,
            water_by_map,
            trees_by_map,
            mines_by_map,
            anvils_by_map,
            forges_by_map,
            signs_by_map,
            doors_by_map,
        )
        if not map_ids:
            log.warning("No se encontraron datos de recursos en %s", maps_dir)
            return

        build_public_structures(
            resources,
            signs,
            doors,
            map_ids,
            blocked_by_map,
            water_by_map,
            trees_by_map,
            mines_by_map,
            anvils_by_map,
            forges_by_map,
            signs_by_map,
            doors_by_map,
            log=log,
        )

        elapsed_time = time.time() - start_time
        log.info(
            "✓ Recursos cargados desde %s: %d mapas en %.2f segundos",
            maps_dir,
            len(resources),
            elapsed_time,
        )

    except Exception:
        log.exception("Error cargando recursos de mapas")
