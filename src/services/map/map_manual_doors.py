"""Puertas definidas manualmente en ``map_doors.toml``."""

from __future__ import annotations

import logging
import tomllib
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.game.map_manager import MapManager

DoorsDict = dict[str, dict[tuple[int, int], int]]


def load_manual_doors(
    doors_config_path: Path,
    doors: DoorsDict,
    map_manager: MapManager | None,
    *,
    log: logging.Logger,
) -> None:
    """Lee puertas desde TOML y opcionalmente bloquea tiles cerrados en ``MapManager``."""
    if not doors_config_path.exists():
        log.info("No se encontró archivo de configuración de puertas: %s", doors_config_path)
        return

    try:
        with doors_config_path.open("rb") as f:
            data = tomllib.load(f)

        door_count = 0
        for door in data.get("door", []):
            map_id = door.get("map_id")
            x = door.get("x")
            y = door.get("y")
            grh_index = door.get("grh_index")

            if not all([map_id, x, y, grh_index]):
                log.warning("Puerta con datos incompletos: %s", door)
                continue

            map_key = f"map_{map_id}"
            if map_key not in doors:
                doors[map_key] = {}

            doors[map_key][x, y] = grh_index
            door_count += 1

            is_open = door.get("is_open", False)
            if not is_open and map_manager:
                map_manager.block_tile(map_id, x, y)
                log.debug("Puerta inicializada como cerrada en (%d, %d, %d)", map_id, x, y)

            log.debug(
                "Puerta cargada: Mapa %d (%d, %d) - GrhIndex=%d - %s - Estado: %s",
                map_id,
                x,
                y,
                grh_index,
                door.get("name", "Sin nombre"),
                "abierta" if is_open else "cerrada",
            )

        log.info("✓ Cargadas %d puertas desde configuración manual", door_count)

    except Exception:
        log.exception("Error cargando puertas manuales")
