"""Servicio para gestionar recursos del mapa (agua, árboles, minas)."""

import json
import logging
import time
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
        start_time = time.time()
        try:
            if not self.maps_dir.exists():
                logger.warning("Directorio de mapas no encontrado: %s", self.maps_dir)
                self.maps_dir.mkdir(parents=True, exist_ok=True)
                return

            map_ids: set[int] = set()

            # Buscar archivos con formato: blocked_XXX-YYY.json y objects_XXX-YYY.json
            for file_pattern in ["blocked_*.json", "objects_*.json"]:
                for data_file in self.maps_dir.glob(file_pattern):
                    try:
                        # Extraer rango del nombre: blocked_001-050.json -> [001, 050]
                        stem = data_file.stem  # "blocked_001-050"
                        range_part = stem.split("_")[1]  # "001-050"
                        start_map = int(range_part.split("-")[0])
                        end_map = int(range_part.split("-")[1])

                        # Agregar todos los mapas del rango
                        map_ids.update(range(start_map, end_map + 1))
                    except (ValueError, IndexError):
                        logger.warning(
                            "Ignorando archivo con nombre inválido: %s",
                            data_file.name,
                        )

            if not map_ids:
                logger.warning("No se encontraron archivos de mapas en %s", self.maps_dir)
                return

            for map_id in sorted(map_ids):
                self._load_map(map_id)

            elapsed_time = time.time() - start_time
            logger.info(
                "✓ Recursos cargados desde %s: %d mapas en %.2f segundos",
                self.maps_dir,
                len(self.resources),
                elapsed_time,
            )

        except Exception:
            logger.exception("Error cargando recursos de mapas")

    def _find_file_for_map(self, pattern: str, map_id: int) -> Path | None:
        """Encuentra el archivo que contiene el mapa especificado.

        Args:
            pattern: Patrón glob para buscar archivos (ej: "blocked_*.json").
            map_id: ID del mapa a buscar.

        Returns:
            Path del archivo encontrado o None.
        """
        for file_path in self.maps_dir.glob(pattern):
            try:
                stem = file_path.stem
                range_part = stem.split("_")[1]
                start_map = int(range_part.split("-")[0])
                end_map = int(range_part.split("-")[1])

                if start_map <= map_id <= end_map:
                    return file_path
            except (ValueError, IndexError):
                continue
        return None

    @staticmethod
    def _process_blocked_file(
        blocked_path: Path | None, map_id: int
    ) -> tuple[
        set[tuple[int, int]], set[tuple[int, int]], set[tuple[int, int]], set[tuple[int, int]]
    ]:
        """Procesa el archivo blocked para extraer tiles bloqueados, agua, árboles y minas.

        Args:
            blocked_path: Path al archivo blocked o None.
            map_id: ID del mapa a filtrar.

        Returns:
            Tupla con (blocked, water, trees, mines).
        """
        blocked: set[tuple[int, int]] = set()
        water: set[tuple[int, int]] = set()
        trees: set[tuple[int, int]] = set()
        mines: set[tuple[int, int]] = set()

        if not blocked_path or not blocked_path.exists():
            return blocked, water, trees, mines

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

                # Filtrar por mapa específico
                if entry.get("m") != map_id:
                    continue

                tile_type = entry.get("t")
                x = entry.get("x")
                y = entry.get("y")

                if not isinstance(x, int) or not isinstance(y, int):
                    continue

                # Convertir tipos compactos a nombres completos
                if tile_type == "b":  # blocked
                    blocked.add((x, y))
                elif tile_type == "w":  # water
                    water.add((x, y))
                    blocked.add((x, y))
                elif tile_type == "t":  # tree
                    trees.add((x, y))
                    blocked.add((x, y))
                elif tile_type == "m":  # mine
                    mines.add((x, y))
                    blocked.add((x, y))

        return blocked, water, trees, mines

    @staticmethod
    def _process_objects_file(
        objects_path: Path | None,
        map_id: int,
        trees: set[tuple[int, int]],
        mines: set[tuple[int, int]],
        blocked: set[tuple[int, int]],
    ) -> None:
        """Procesa el archivo objects para agregar árboles y minas.

        Args:
            objects_path: Path al archivo objects o None.
            map_id: ID del mapa a procesar.
            trees: Set de árboles a actualizar.
            mines: Set de minas a actualizar.
            blocked: Set de bloqueados a actualizar.
        """
        if not objects_path or not objects_path.exists():
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

                # FILTRAR POR MAP_ID
                entry_map_id = entry.get("m")
                if entry_map_id != map_id:
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

    def _load_map(self, map_id: int) -> None:
        """Carga un mapa específico desde sus archivos de datos disponibles.

        Args:
            map_id: ID del mapa.
        """
        map_key = f"map_{map_id}"

        # Encontrar archivos que contienen este mapa
        blocked_path = self._find_file_for_map("blocked_*.json", map_id)
        objects_path = self._find_file_for_map("objects_*.json", map_id)

        if blocked_path is None and objects_path is None:
            logger.debug("No se encontraron archivos de datos para mapa %d", map_id)
            return

        try:
            blocked, water, trees, mines = self._process_blocked_file(blocked_path, map_id)

            # Cargar árboles y minas desde archivo objects
            self._process_objects_file(objects_path, map_id, trees, mines, blocked)

            # Determinar fuente de datos para logging
            if blocked_path and objects_path:
                blocked_name = blocked_path.name if blocked_path else "(sin blocked)"
                source = f"{blocked_name} + {objects_path.name}"
            else:
                source = (
                    blocked_path.name
                    if blocked_path
                    else (objects_path.name if objects_path else "unknown")
                )

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
