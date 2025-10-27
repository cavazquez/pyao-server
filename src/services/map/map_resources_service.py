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

            map_ids: set[int] = set()

            for blocked_file in self.maps_dir.glob("*_blocked.json"):
                try:
                    map_ids.add(int(blocked_file.stem.split("_")[0]))
                except (ValueError, IndexError):
                    logger.warning(
                        "Ignorando archivo blocked con nombre inválido: %s",
                        blocked_file.name,
                    )

            if not map_ids:
                logger.warning("No se encontraron archivos de mapas en %s", self.maps_dir)
                return

            for map_id in sorted(map_ids):
                self._load_map(map_id)

            logger.info("Recursos cargados desde %s (%d mapas)", self.maps_dir, len(self.resources))

        except Exception:
            logger.exception("Error cargando recursos de mapas")

    def _load_map(self, map_id: int) -> None:
        """Carga un mapa específico desde sus archivos de datos disponibles.

        Args:
            map_id: ID del mapa.
        """
        map_key = f"map_{map_id}"
        blocked_path = self.maps_dir / f"{map_id:03d}_blocked.json"

        try:
            blocked: set[tuple[int, int]] = set()
            water: set[tuple[int, int]] = set()
            trees: set[tuple[int, int]] = set()
            mines: set[tuple[int, int]] = set()

            if blocked_path.exists():
                with blocked_path.open(encoding="utf-8") as f:
                    for line_number, raw_line in enumerate(f, start=1):
                        line = raw_line.strip()
                        if not line:
                            continue
                        try:
                            entry = json.loads(line)
                        except json.JSONDecodeError:
                            logger.debug(
                                "Entrada inválida en %s línea %d: %s",
                                blocked_path.name,
                                line_number,
                                line,
                            )
                            continue

                        tile_type = entry.get("type")
                        x = entry.get("x")
                        y = entry.get("y")

                        if not isinstance(x, int) or not isinstance(y, int):
                            continue

                        if tile_type == "blocked":
                            blocked.add((x, y))
                        elif tile_type == "water":
                            water.add((x, y))
                            blocked.add((x, y))
                        elif tile_type == "tree":
                            trees.add((x, y))
                            blocked.add((x, y))
                        elif tile_type == "mine":
                            mines.add((x, y))
                            blocked.add((x, y))

                source = blocked_path.name
            else:
                logger.warning("No se encontraron datos de recursos para mapa %03d", map_id)
                source = "(sin datos)"

            self.resources[map_key] = {
                "blocked": blocked,
                "water": water,
                "trees": trees,
                "mines": mines,
            }

            logger.info(
                "  %s (%s): %d agua, %d árboles, %d minas",
                map_key,
                source,
                len(water),
                len(trees),
                len(mines),
            )

        except Exception:
            logger.exception("Error cargando datos de recursos para mapa %d", map_id)

    def is_blocked(self, map_id: int, x: int, y: int) -> bool:
        """Indica si un tile está marcado como bloqueado en el mapa.

        Args:
            map_id: ID del mapa.
            x: Coordenada X.
            y: Coordenada Y.

        Returns:
            True si el tile está bloqueado, False en caso contrario.
        """
        map_key = f"map_{map_id}"
        if map_key not in self.resources:
            return False
        return (x, y) in self.resources[map_key]["blocked"]

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
