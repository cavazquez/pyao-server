"""Talleres estáticos del archivo de objetos .inf del Argentum original."""

import logging
import tomllib
from pathlib import Path

from src.game.coordinate_mask import CoordinateMask, ResourcesMap

logger = logging.getLogger(__name__)
Workshops = dict[int, list[tuple[int, int, int]]]
MAP_SIZE = 100
MAX_GRAPHIC = 32767


def load_workshops(path: Path, resources: ResourcesMap) -> Workshops:
    """Añade talleres al terreno después de cargar cualquier caché de mapas.

    Returns:
        Coordenadas y gráfico que deben recibir los clientes al entrar al mapa.

    Raises:
        ValueError: Si el catálogo contiene coordenadas o tipos inválidos.
    """
    if not path.is_file():
        return {}
    with path.open("rb") as source:
        data = tomllib.load(source)
    result: Workshops = {}
    seen: set[tuple[int, int, int]] = set()
    for row in data.get("workshop", []):
        map_id, x, y, graphic = (row.get(key) for key in ("map_id", "x", "y", "grh_index"))
        layer = {"anvil": "anvils", "forge": "forges"}.get(row.get("kind"))
        valid_coordinates = (
            all(type(value) is int for value in (map_id, x, y, graphic))
            and map_id > 0
            and 1 <= x <= MAP_SIZE
            and 1 <= y <= MAP_SIZE
            and 0 < graphic <= MAX_GRAPHIC
        )
        if not valid_coordinates or layer is None or (map_id, x, y) in seen:
            message = f"Taller inválido: {row!r}"
            raise ValueError(message)
        seen.add((map_id, x, y))
        terrain = resources.get(f"map_{map_id}")
        if terrain is None:
            continue
        terrain.setdefault(layer, CoordinateMask()).add((x, y))
        terrain["blocked"].add((x, y))
        result.setdefault(map_id, []).append((x, y, graphic))
    logger.info("✓ Cargados %d talleres estáticos", sum(map(len, result.values())))
    return result
