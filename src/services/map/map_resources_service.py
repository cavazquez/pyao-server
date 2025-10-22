"""Servicio para gestionar recursos del mapa (agua, árboles, minas)."""

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class MapResourcesService:
    """Servicio que gestiona los recursos de los mapas (agua, árboles, yacimientos)."""

    def __init__(self, maps_dir: str | Path | None = None) -> None:
        """Inicializa el servicio de recursos.

        Args:
            maps_dir: Directorio con los archivos JSON de recursos (opcional).
        """
        self.maps_dir = Path(maps_dir) if maps_dir else Path("map_data")
        self.resources: dict[str, dict[str, set[tuple[int, int]]]] = {}
        self._load_all_maps()

    def _load_all_maps(self) -> None:
        """Carga todos los mapas desde el directorio."""
        try:
            if not self.maps_dir.exists():
                logger.warning("Directorio de mapas no encontrado: %s", self.maps_dir)
                self.maps_dir.mkdir(parents=True, exist_ok=True)
                return

            # Buscar archivos de recursos (formato: XXX_resources.json)
            map_files = list(self.maps_dir.glob("*_resources.json"))

            if not map_files:
                logger.warning("No se encontraron archivos de mapas en %s", self.maps_dir)
                return

            for map_file in map_files:
                # Extraer map_id del nombre (ej: "001_resources.json" -> 1)
                try:
                    map_id = int(map_file.stem.split("_")[0])
                    self._load_map(map_id, map_file)
                except (ValueError, IndexError):
                    logger.warning("Ignorando archivo con nombre inválido: %s", map_file.name)
                    continue

            logger.info("Recursos cargados desde %s (%d mapas)", self.maps_dir, len(self.resources))

        except Exception:
            logger.exception("Error cargando recursos de mapas")

    def _load_map(self, map_id: int, map_file: Path) -> None:
        """Carga un mapa específico desde su archivo JSON.

        Args:
            map_id: ID del mapa.
            map_file: Archivo JSON del mapa.
        """
        try:
            with map_file.open(encoding="utf-8") as f:
                data = json.load(f)

            map_key = f"map_{map_id}"
            self.resources[map_key] = {
                "water": {tuple(coord) for coord in data.get("water", [])},
                "trees": {tuple(coord) for coord in data.get("trees", [])},
                "mines": {tuple(coord) for coord in data.get("mines", [])},
            }

            logger.info(
                "  %s: %d agua, %d árboles, %d minas",
                map_key,
                len(self.resources[map_key]["water"]),
                len(self.resources[map_key]["trees"]),
                len(self.resources[map_key]["mines"]),
            )

        except Exception:
            logger.exception("Error cargando mapa %d desde %s", map_id, map_file)

    def has_water(self, map_id: int, x: int, y: int) -> bool:
        """Verifica si una posición tiene agua.

        Args:
            map_id: ID del mapa.
            x: Coordenada X.
            y: Coordenada Y.

        Returns:
            True si hay agua, False si no.
        """
        map_key = f"map_{map_id}"
        if map_key not in self.resources:
            return False
        return (x, y) in self.resources[map_key]["water"]

    def has_tree(self, map_id: int, x: int, y: int) -> bool:
        """Verifica si una posición tiene un árbol.

        Args:
            map_id: ID del mapa.
            x: Coordenada X.
            y: Coordenada Y.

        Returns:
            True si hay un árbol, False si no.
        """
        map_key = f"map_{map_id}"
        if map_key not in self.resources:
            return False
        return (x, y) in self.resources[map_key]["trees"]

    def has_mine(self, map_id: int, x: int, y: int) -> bool:
        """Verifica si una posición tiene un yacimiento de minerales.

        Args:
            map_id: ID del mapa.
            x: Coordenada X.
            y: Coordenada Y.

        Returns:
            True si hay un yacimiento, False si no.
        """
        map_key = f"map_{map_id}"
        if map_key not in self.resources:
            return False
        return (x, y) in self.resources[map_key]["mines"]

    def get_resource_counts(self, map_id: int) -> dict[str, int]:
        """Obtiene el conteo de recursos en un mapa.

        Args:
            map_id: ID del mapa.

        Returns:
            Diccionario con conteos de recursos.
        """
        map_key = f"map_{map_id}"
        if map_key not in self.resources:
            return {"water": 0, "trees": 0, "mines": 0}

        return {
            "water": len(self.resources[map_key]["water"]),
            "trees": len(self.resources[map_key]["trees"]),
            "mines": len(self.resources[map_key]["mines"]),
        }
