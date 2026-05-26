"""Servicio para gestionar recursos del mapa (agua, árboles, minas)."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from src.services.map.binary_cache import MapBinaryCache
from src.services.map.cache import MapCacheLoader
from src.services.map.map_bulk_resources_loader import run_load_all_maps
from src.services.map.map_manual_doors import load_manual_doors
from src.services.map.map_resource_queries import (
    get_door_at,
    get_resource_counts,
    get_sign_at,
    tile_in_optional_layer,
    tile_in_required_layer,
)
from src.services.map.map_single_map_loader import load_single_map_into

if TYPE_CHECKING:
    from src.game.map_manager import MapManager

logger = logging.getLogger(__name__)


def resolve_manual_doors_config_path() -> Path:
    """Ruta a ``data/world/map_doors.toml`` (repo o jerarquía Snap)."""
    snap_common = os.environ.get("SNAP_USER_COMMON")
    if snap_common:
        return Path(snap_common) / "data/world/map_doors.toml"
    return Path(__file__).resolve().parent.parent.parent.parent / "data/world/map_doors.toml"


class MapResourcesService:
    """Servicio que gestiona los recursos de los mapas (agua, árboles, yacimientos)."""

    def __init__(
        self, maps_dir: str | Path | None = None, map_manager: MapManager | None = None
    ) -> None:
        """Inicializa el servicio de recursos.

        Args:
            maps_dir: Directorio con los archivos JSON de recursos (opcional).
            map_manager: MapManager para inicializar puertas cerradas (opcional).
        """
        self.maps_dir = Path(maps_dir) if maps_dir is not None else Path("map_data")
        self._fatal_on_missing_resources = maps_dir is None and self.maps_dir == Path("map_data")

        self.cache_dir = Path("map_cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.resources: dict[str, dict[str, set[tuple[int, int]]]] = {}
        self.signs: dict[str, dict[tuple[int, int], int]] = {}
        self.doors: dict[str, dict[tuple[int, int], int]] = {}

        self.map_manager = map_manager

        self._cache_loader = MapCacheLoader(self.maps_dir, self.cache_dir)
        binary_loader = MapBinaryCache(self.maps_dir, self.resources, self.signs, self.doors)

        loaded = binary_loader.try_load_from_binary()

        if not loaded:
            loaded = self._cache_loader.try_load_from_cache(self.resources, self.signs, self.doors)

        if not loaded:
            self._load_all_maps()
            if self.resources:
                self._cache_loader.save_cache(self.resources, self.signs, self.doors)
                binary_loader.generate_binary_cache()
            else:
                msg = (
                    "MapResourcesService: no se encontraron recursos en %s; "
                    "ejecuta 'uv run python -m tools.compression.map_sync pull'"
                )
                logger.warning(msg, self.maps_dir)
                if self._fatal_on_missing_resources:
                    sys.exit(msg % self.maps_dir)

        self._load_manual_doors()

    def _load_all_maps(self) -> None:
        """Carga todos los mapas desde el directorio."""
        run_load_all_maps(
            self.maps_dir,
            self.resources,
            self.signs,
            self.doors,
            log=logger,
        )

    def _load_map(self, map_id: int) -> None:
        load_single_map_into(
            self.resources,
            self.signs,
            self.doors,
            self.maps_dir,
            map_id,
            log=logger,
        )

    def is_blocked(self, map_id: int, x: int, y: int) -> bool:
        """Indica si un tile está marcado como bloqueado en el mapa."""
        return tile_in_required_layer(self.resources, map_id, "blocked", x, y)

    def has_water(self, map_id: int, x: int, y: int) -> bool:
        """Verifica si una posición tiene agua."""
        return tile_in_required_layer(self.resources, map_id, "water", x, y)

    def has_tree(self, map_id: int, x: int, y: int) -> bool:
        """Verifica si una posición tiene un árbol."""
        return tile_in_required_layer(self.resources, map_id, "trees", x, y)

    def has_mine(self, map_id: int, x: int, y: int) -> bool:
        """Verifica si una posición tiene un yacimiento de minerales."""
        return tile_in_required_layer(self.resources, map_id, "mines", x, y)

    def has_anvil(self, map_id: int, x: int, y: int) -> bool:
        """Verifica si una posición tiene un yunque."""
        return tile_in_optional_layer(self.resources, map_id, "anvils", x, y)

    def has_forge(self, map_id: int, x: int, y: int) -> bool:
        """Verifica si una posición tiene una fragua."""
        return tile_in_optional_layer(self.resources, map_id, "forges", x, y)

    def get_resource_counts(self, map_id: int) -> dict[str, int]:
        """Obtiene el conteo de recursos en un mapa."""
        return get_resource_counts(self.resources, self.signs, self.doors, map_id)

    def get_sign_at(self, map_id: int, x: int, y: int) -> int | None:
        """Obtiene el GrhIndex del cartel en una posición."""
        return get_sign_at(self.signs, map_id, x, y)

    def get_door_at(self, map_id: int, x: int, y: int) -> int | None:
        """Obtiene el GrhIndex de la puerta en una posición."""
        return get_door_at(self.doors, map_id, x, y)

    def _load_manual_doors(self) -> None:
        load_manual_doors(
            resolve_manual_doors_config_path(), self.doors, self.map_manager, log=logger
        )
