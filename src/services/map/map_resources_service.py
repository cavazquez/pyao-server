"""Servicio para gestionar recursos del mapa (agua, árboles, minas)."""

from __future__ import annotations

import json
import logging
import sys
import time
import tomllib
from collections import defaultdict
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.game.map_manager import MapManager

logger = logging.getLogger(__name__)

MAP_RESOURCES_CACHE_VERSION = 2


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
        # Directorio de origen de datos de mapas (blocked_*.json, objects_*.json, etc.)
        self.maps_dir = Path(maps_dir) if maps_dir is not None else Path("map_data")
        # Solo consideramos "fatal" la falta de recursos cuando se usa el valor por
        # defecto (map_data/) y no se especificó maps_dir explícitamente (por ejemplo,
        # en tests o herramientas de consola).
        self._fatal_on_missing_resources = maps_dir is None and self.maps_dir == Path("map_data")

        # Directorio para cachés derivados (map_resources_cache.json)
        self.cache_dir = Path("map_cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.resources: dict[str, dict[str, set[tuple[int, int]]]] = {}
        self.signs: dict[str, dict[tuple[int, int], int]] = {}  # map_key -> {(x,y): grh_index}
        self.doors: dict[str, dict[tuple[int, int], int]] = {}  # map_key -> {(x,y): grh_index}

        # Estructuras internas para acumulación por mapa durante la carga
        self._blocked_by_map: dict[int, set[tuple[int, int]]] = {}
        self._water_by_map: dict[int, set[tuple[int, int]]] = {}
        self._trees_by_map: dict[int, set[tuple[int, int]]] = {}
        self._mines_by_map: dict[int, set[tuple[int, int]]] = {}
        self._anvils_by_map: dict[int, set[tuple[int, int]]] = {}
        self._forges_by_map: dict[int, set[tuple[int, int]]] = {}
        self._signs_by_map: dict[int, dict[tuple[int, int], int]] = {}
        self._doors_by_map: dict[int, dict[tuple[int, int], int]] = {}
        self.map_manager = map_manager

        # Intentar cargar desde caché en disco primero
        if not self._try_load_from_cache():
            self._load_all_maps()
            if self.resources:
                self._save_cache()
            else:
                msg = (
                    "MapResourcesService: no se encontraron recursos en %s; "
                    "ejecuta 'uv run tools/decompress_map_data.py' para generar map_data/"
                )
                logger.warning(msg, self.maps_dir)
                if self._fatal_on_missing_resources:
                    # Cortar la inicialización del servidor cuando no hay datos de mapas
                    # y se está usando la configuración por defecto.
                    sys.exit(msg % self.maps_dir)
        self._load_manual_doors()

    def _load_all_maps(self) -> None:
        """Carga todos los mapas desde el directorio."""
        start_time = time.time()
        try:
            if not self.maps_dir.exists():
                logger.warning("Directorio de mapas no encontrado: %s", self.maps_dir)
                self.maps_dir.mkdir(parents=True, exist_ok=True)
                return

            # Estructuras internas para acumular datos por mapa durante la carga
            self._blocked_by_map = defaultdict(set)
            self._water_by_map = defaultdict(set)
            self._trees_by_map = defaultdict(set)
            self._mines_by_map = defaultdict(set)
            self._anvils_by_map = defaultdict(set)
            self._forges_by_map = defaultdict(set)
            self._signs_by_map = {}
            self._doors_by_map = {}

            # Procesar archivos blocked_*.json una sola vez cada uno
            blocked_files = sorted(self.maps_dir.glob("blocked_*.json"))
            objects_files = sorted(self.maps_dir.glob("objects_*.json"))

            if not blocked_files and not objects_files:
                logger.warning("No se encontraron archivos de mapas en %s", self.maps_dir)
                return

            for blocked_path in blocked_files:
                self._process_blocked_file_per_file(
                    blocked_path,
                    self._blocked_by_map,
                    self._water_by_map,
                    self._trees_by_map,
                    self._mines_by_map,
                )

            for objects_path in objects_files:
                self._process_objects_file_per_file(
                    objects_path,
                    self._trees_by_map,
                    self._mines_by_map,
                    self._blocked_by_map,
                    self._signs_by_map,
                    self._doors_by_map,
                    self._water_by_map,
                    self._anvils_by_map,
                    self._forges_by_map,
                )

            # Unificar todos los IDs de mapa que tienen algún recurso
            map_ids: set[int] = set(self._blocked_by_map.keys())
            map_ids.update(self._water_by_map.keys())
            map_ids.update(self._trees_by_map.keys())
            map_ids.update(self._mines_by_map.keys())
            map_ids.update(self._anvils_by_map.keys())
            map_ids.update(self._forges_by_map.keys())
            map_ids.update(self._signs_by_map.keys())
            map_ids.update(self._doors_by_map.keys())

            if not map_ids:
                logger.warning("No se encontraron datos de recursos en %s", self.maps_dir)
                return

            # Construir estructuras públicas (resources, signs, doors) a partir de los acumuladores
            for map_id in sorted(map_ids):
                map_key = f"map_{map_id}"

                blocked = self._blocked_by_map.get(map_id, set())
                water = self._water_by_map.get(map_id, set())
                trees = self._trees_by_map.get(map_id, set())
                mines = self._mines_by_map.get(map_id, set())
                anvils = self._anvils_by_map.get(map_id, set())
                forges = self._forges_by_map.get(map_id, set())

                self.resources[map_key] = {
                    "blocked": blocked,
                    "water": water,
                    "trees": trees,
                    "mines": mines,
                    "anvils": anvils,
                    "forges": forges,
                }

                if map_id in self._signs_by_map:
                    self.signs[map_key] = self._signs_by_map[map_id]

                if map_id in self._doors_by_map:
                    self.doors[map_key] = self._doors_by_map[map_id]

                signs_count = len(self._signs_by_map.get(map_id, {}))
                doors_count = len(self._doors_by_map.get(map_id, {}))

                logger.info(
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

            elapsed_time = time.time() - start_time
            logger.info(
                "✓ Recursos cargados desde %s: %d mapas en %.2f segundos",
                self.maps_dir,
                len(self.resources),
                elapsed_time,
            )

        except Exception:
            logger.exception("Error cargando recursos de mapas")

    def _try_load_from_cache(self) -> bool:
        """Intenta cargar recursos de mapas desde el caché en disco.

        Returns:
            True si el caché es válido y fue cargado correctamente.
        """
        cache_path = self.cache_dir / "map_resources_cache.json"
        start_time = time.time()
        if not cache_path.exists():
            return False

        try:
            data = self._read_cache_file(cache_path)
        except (OSError, json.JSONDecodeError):
            logger.warning("No se pudo leer caché de mapas: %s", cache_path)
            return False

        if data.get("version") != MAP_RESOURCES_CACHE_VERSION:
            return False

        source = data.get("source") or {}
        if not isinstance(source, dict):
            return False

        blocked_info = source.get("blocked") or {}
        objects_info = source.get("objects") or {}
        if not isinstance(blocked_info, dict) or not isinstance(objects_info, dict):
            return False

        blocked_files = sorted(self.maps_dir.glob("blocked_*.json"))
        objects_files = sorted(self.maps_dir.glob("objects_*.json"))

        if not self._is_cache_source_valid(
            blocked_files,
            objects_files,
            blocked_info,
            objects_info,
        ):
            return False

        maps_data = data.get("maps")
        if not isinstance(maps_data, dict):
            return False

        try:
            self._rebuild_resources_from_cache(maps_data)
        except Exception:
            logger.exception("Error cargando recursos de mapas desde caché")
            self.resources.clear()
            self.signs.clear()
            self.doors.clear()
            return False
        else:
            elapsed_time = time.time() - start_time
            logger.info(
                "✓ Recursos de mapas cargados desde caché: %s en %.3f segundos",
                cache_path,
                elapsed_time,
            )
            return True

    def _save_cache(self) -> None:
        """Guarda los recursos de mapas en caché en disco."""
        cache_path = self.cache_dir / "map_resources_cache.json"

        blocked_files = sorted(self.maps_dir.glob("blocked_*.json"))
        objects_files = sorted(self.maps_dir.glob("objects_*.json"))
        blocked_names, blocked_mtimes = self._build_mtimes(blocked_files)
        objects_names, objects_mtimes = self._build_mtimes(objects_files)

        maps_payload = self._build_maps_payload_for_cache()

        payload = {
            "version": MAP_RESOURCES_CACHE_VERSION,
            "source": {
                "blocked": {"files": blocked_names, "mtimes": blocked_mtimes},
                "objects": {"files": objects_names, "mtimes": objects_mtimes},
            },
            "maps": maps_payload,
        }

        try:
            with cache_path.open("w", encoding="utf-8") as f:
                json.dump(payload, f)
            logger.info("✓ Caché de recursos de mapas guardado en %s", cache_path)
        except OSError:
            logger.exception("Error guardando caché de recursos de mapas en %s", cache_path)

    @staticmethod
    def _build_mtimes(files: list[Path]) -> tuple[list[str], dict[str, float]]:
        """Construye listas de nombres y mtimes para una lista de paths.

        Returns:
            Tupla ``(names, mtimes)`` donde ``names`` es la lista de nombres de
            archivo y ``mtimes`` un diccionario ``nombre -> mtime``.
        """
        names: list[str] = []
        mtimes: dict[str, float] = {}
        for fp in files:
            try:
                stat = fp.stat()
            except OSError:
                continue
            name = fp.name
            names.append(name)
            mtimes[name] = stat.st_mtime
        return names, mtimes

    @staticmethod
    def _read_cache_file(cache_path: Path) -> dict[str, object]:
        """Lee y parsea el archivo de caché de mapas.

        Returns:
            Diccionario raíz del archivo de caché.

        Raises:
            JSONDecodeError: Si el contenido del archivo no es un objeto JSON
            de nivel raíz (dict).
        """
        with cache_path.open(encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):  # Defensa extra para mypy y robustez
            msg = "Cache root is not a dict"
            raise json.JSONDecodeError(msg, doc="", pos=0)
        return data

    @staticmethod
    def _is_cache_source_valid(
        blocked_files: list[Path],
        objects_files: list[Path],
        blocked_info: dict[str, object],
        objects_info: dict[str, object],
    ) -> bool:
        """Valida que los archivos y mtimes actuales coinciden con el caché.

        Returns:
            ``True`` si los nombres y mtimes de los archivos actuales coinciden
            exactamente con los almacenados en el caché, ``False`` en caso
            contrario.
        """
        current_blocked_names, current_blocked_mtimes = MapResourcesService._build_mtimes(
            blocked_files
        )
        current_objects_names, current_objects_mtimes = MapResourcesService._build_mtimes(
            objects_files
        )

        if blocked_info.get("files") != current_blocked_names:
            return False
        if objects_info.get("files") != current_objects_names:
            return False

        if blocked_info.get("mtimes") != current_blocked_mtimes:
            return False
        return objects_info.get("mtimes") == current_objects_mtimes

    def _rebuild_resources_from_cache(self, maps_data: dict[str, object]) -> None:  # noqa: PLR0914
        """Reconstruye resources, signs y doors a partir del payload del caché."""
        self.resources.clear()
        self.signs.clear()
        self.doors.clear()

        for map_id_str, map_payload_obj in maps_data.items():
            if not isinstance(map_payload_obj, dict):
                continue

            try:
                map_id = int(map_id_str)
            except (TypeError, ValueError):
                continue

            map_key = f"map_{map_id}"
            blocked_list = map_payload_obj.get("blocked", [])
            water_list = map_payload_obj.get("water", [])
            trees_list = map_payload_obj.get("trees", [])
            mines_list = map_payload_obj.get("mines", [])
            anvils_list = map_payload_obj.get("anvils", [])
            forges_list = map_payload_obj.get("forges", [])

            blocked = {(int(x), int(y)) for x, y in blocked_list}
            water = {(int(x), int(y)) for x, y in water_list}
            trees = {(int(x), int(y)) for x, y in trees_list}
            mines = {(int(x), int(y)) for x, y in mines_list}
            anvils = {(int(x), int(y)) for x, y in anvils_list}
            forges = {(int(x), int(y)) for x, y in forges_list}

            self.resources[map_key] = {
                "blocked": blocked,
                "water": water,
                "trees": trees,
                "mines": mines,
                "anvils": anvils,
                "forges": forges,
            }

            signs_list = map_payload_obj.get("signs", [])
            if signs_list:
                signs_dict: dict[tuple[int, int], int] = {}
                for coord, grh in signs_list:
                    x, y = coord
                    if isinstance(grh, int):
                        signs_dict[int(x), int(y)] = grh
                if signs_dict:
                    self.signs[map_key] = signs_dict

            doors_list = map_payload_obj.get("doors", [])
            if doors_list:
                doors_dict: dict[tuple[int, int], int] = {}
                for coord, grh in doors_list:
                    x, y = coord
                    if isinstance(grh, int):
                        doors_dict[int(x), int(y)] = grh
                if doors_dict:
                    self.doors[map_key] = doors_dict

    def _build_maps_payload_for_cache(self) -> dict[str, dict[str, object]]:
        """Construye el payload de mapas a guardar en el archivo de caché.

        Returns:
            Diccionario ``{map_id_str: payload}`` listo para serializar en el
            archivo de caché.
        """
        maps_payload: dict[str, dict[str, object]] = {}
        for map_key, res in self.resources.items():
            if not map_key.startswith("map_"):
                continue
            try:
                map_id = int(map_key.split("_")[1])
            except (IndexError, ValueError):
                continue

            blocked = list(res.get("blocked", set()))
            water = list(res.get("water", set()))
            trees = list(res.get("trees", set()))
            mines = list(res.get("mines", set()))
            anvils = list(res.get("anvils", set()))
            forges = list(res.get("forges", set()))

            map_entry: dict[str, object] = {
                "blocked": blocked,
                "water": water,
                "trees": trees,
                "mines": mines,
                "anvils": anvils,
                "forges": forges,
            }

            signs_dict = self.signs.get(map_key)
            if signs_dict:
                signs_list = [((x, y), grh) for (x, y), grh in signs_dict.items()]
                map_entry["signs"] = signs_list

            doors_dict = self.doors.get(map_key)
            if doors_dict:
                doors_list = [((x, y), grh) for (x, y), grh in doors_dict.items()]
                map_entry["doors"] = doors_list

            maps_payload[str(map_id)] = map_entry

        return maps_payload

    @staticmethod
    def _process_blocked_file_per_file(
        blocked_path: Path,
        blocked_by_map: dict[int, set[tuple[int, int]]],
        water_by_map: dict[int, set[tuple[int, int]]],
        trees_by_map: dict[int, set[tuple[int, int]]],
        mines_by_map: dict[int, set[tuple[int, int]]],
    ) -> None:
        """Procesa un archivo blocked completo, agrupando por map_id.

        Cada línea representa un tile con un map_id "m". Se acumulan los
        resultados en los diccionarios proporcionados.
        """
        if not blocked_path.exists():
            return

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

                if tile_type == "b":  # blocked
                    blocked_by_map[map_id].add((x, y))
                elif tile_type == "w":  # water
                    water_by_map[map_id].add((x, y))
                    blocked_by_map[map_id].add((x, y))
                elif tile_type == "t":  # tree
                    trees_by_map[map_id].add((x, y))
                    blocked_by_map[map_id].add((x, y))
                elif tile_type == "m":  # mine
                    mines_by_map[map_id].add((x, y))
                    blocked_by_map[map_id].add((x, y))

    @staticmethod
    def _process_objects_file_per_file(
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
        """Procesa un archivo objects completo, agrupando por map_id.

        Extrae árboles, minas, carteles y puertas, actualizando los
        diccionarios correspondientes.
        """
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
                        if map_id not in signs_by_map:
                            signs_by_map[map_id] = {}
                        signs_by_map[map_id][x, y] = grh
                elif tile_type == "door":
                    grh = entry.get("g")
                    if isinstance(grh, int):
                        if map_id not in doors_by_map:
                            doors_by_map[map_id] = {}
                        doors_by_map[map_id][x, y] = grh

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
        water: set[tuple[int, int]],
        anvils: set[tuple[int, int]],
        forges: set[tuple[int, int]],
    ) -> None:
        """Procesa el archivo objects para agregar recursos a un mapa.

        Args:
            objects_path: Path al archivo objects o None.
            map_id: ID del mapa a procesar.
            trees: Set de árboles a actualizar.
            mines: Set de minas a actualizar.
            blocked: Set de tiles bloqueados a actualizar.
            water: Set de tiles con agua a actualizar.
            anvils: Set de tiles con yunques a actualizar.
            forges: Set de tiles con fraguas a actualizar.
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
                elif tile_type == "anvil":
                    anvils.add((x, y))
                    blocked.add((x, y))
                elif tile_type == "forge":
                    forges.add((x, y))
                    blocked.add((x, y))
                elif tile_type == "water":
                    water.add((x, y))
                elif tile_type == "sign":
                    # Los carteles se manejan por separado (necesitamos el GrhIndex)
                    pass

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

            anvils: set[tuple[int, int]] = set()
            forges: set[tuple[int, int]] = set()

            # Cargar árboles, minas, yunques, fraguas y agua adicional desde archivo objects
            self._process_objects_file(
                objects_path,
                map_id,
                trees,
                mines,
                blocked,
                water,
                anvils,
                forges,
            )

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

            # Cargar carteles desde objects file
            signs_dict = self._load_signs_from_objects(objects_path, map_id)
            if signs_dict:
                self.signs[map_key] = signs_dict

            # Cargar puertas desde objects file
            doors_dict = self._load_doors_from_objects(objects_path, map_id)
            if doors_dict:
                self.doors[map_key] = doors_dict

            logger.info(
                "  %s (%s): %d bloqueados, %d agua, %d árboles, %d minas, %d yunques, %d fraguas",
                map_key,
                source,
                len(blocked),
                len(water),
                len(trees),
                len(mines),
                len(anvils),
                len(forges),
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

    def has_anvil(self, map_id: int, x: int, y: int) -> bool:
        """Verifica si una posición tiene un yunque.

        Returns:
            True si hay un yunque, False si no.
        """
        map_key = f"map_{map_id}"
        if map_key not in self.resources:
            return False
        return (x, y) in self.resources[map_key].get("anvils", set())

    def has_forge(self, map_id: int, x: int, y: int) -> bool:
        """Verifica si una posición tiene una fragua.

        Returns:
            True si hay una fragua, False si no.
        """
        map_key = f"map_{map_id}"
        if map_key not in self.resources:
            return False
        return (x, y) in self.resources[map_key].get("forges", set())

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

        signs_count = len(self.signs.get(map_key, {}))
        doors_count = len(self.doors.get(map_key, {}))
        anvils_count = len(self.resources[map_key].get("anvils", set()))
        forges_count = len(self.resources[map_key].get("forges", set()))

        return {
            "water": len(self.resources[map_key]["water"]),
            "trees": len(self.resources[map_key]["trees"]),
            "mines": len(self.resources[map_key]["mines"]),
            "anvils": anvils_count,
            "forges": forges_count,
            "signs": signs_count,
            "doors": doors_count,
        }

    def get_sign_at(self, map_id: int, x: int, y: int) -> int | None:
        """Obtiene el GrhIndex del cartel en una posición.

        Args:
            map_id: ID del mapa.
            x: Coordenada X.
            y: Coordenada Y.

        Returns:
            GrhIndex del cartel o None si no hay cartel.
        """
        map_key = f"map_{map_id}"
        if map_key not in self.signs:
            return None

        return self.signs[map_key].get((x, y))

    @staticmethod
    def _load_signs_from_objects(
        objects_path: Path | None, map_id: int
    ) -> dict[tuple[int, int], int]:
        """Carga carteles desde el archivo objects.

        Args:
            objects_path: Path al archivo objects.
            map_id: ID del mapa.

        Returns:
            Diccionario {(x, y): grh_index} con los carteles.
        """
        signs_dict: dict[tuple[int, int], int] = {}

        if not objects_path or not objects_path.exists():
            return signs_dict

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

                # Filtrar por mapa y tipo
                if entry.get("m") != map_id:
                    continue

                if entry.get("t") != "sign":
                    continue

                x = entry.get("x")
                y = entry.get("y")
                grh = entry.get("g")

                if isinstance(x, int) and isinstance(y, int) and isinstance(grh, int):
                    signs_dict[x, y] = grh

        return signs_dict

    def get_door_at(self, map_id: int, x: int, y: int) -> int | None:
        """Obtiene el GrhIndex de la puerta en una posición.

        Args:
            map_id: ID del mapa.
            x: Coordenada X.
            y: Coordenada Y.

        Returns:
            GrhIndex de la puerta o None si no hay puerta.
        """
        map_key = f"map_{map_id}"
        if map_key not in self.doors:
            return None

        return self.doors[map_key].get((x, y))

    @staticmethod
    def _load_doors_from_objects(
        objects_path: Path | None, map_id: int
    ) -> dict[tuple[int, int], int]:
        """Carga puertas desde el archivo objects.

        Args:
            objects_path: Path al archivo objects.
            map_id: ID del mapa.

        Returns:
            Diccionario {(x, y): grh_index} con las puertas.
        """
        doors_dict: dict[tuple[int, int], int] = {}

        if not objects_path or not objects_path.exists():
            return doors_dict

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

                # Filtrar por mapa y tipo
                if entry.get("m") != map_id:
                    continue

                if entry.get("t") != "door":
                    continue

                x = entry.get("x")
                y = entry.get("y")
                grh = entry.get("g")

                if isinstance(x, int) and isinstance(y, int) and isinstance(grh, int):
                    doors_dict[x, y] = grh

        return doors_dict

    def _load_manual_doors(self) -> None:
        """Carga puertas desde el archivo de configuración manual.

        Las puertas no están en los archivos .map del servidor VB6,
        por lo que se definen manualmente en data/world/map_doors.toml
        """
        doors_config_path = Path(__file__).parent.parent.parent.parent / "data/world/map_doors.toml"

        if not doors_config_path.exists():
            logger.info("No se encontró archivo de configuración de puertas: %s", doors_config_path)
            return

        try:
            with Path(doors_config_path).open("rb") as f:
                data = tomllib.load(f)

            door_count = 0
            for door in data.get("door", []):
                map_id = door.get("map_id")
                x = door.get("x")
                y = door.get("y")
                grh_index = door.get("grh_index")

                if not all([map_id, x, y, grh_index]):
                    logger.warning("Puerta con datos incompletos: %s", door)
                    continue

                map_key = f"map_{map_id}"
                if map_key not in self.doors:
                    self.doors[map_key] = {}

                self.doors[map_key][x, y] = grh_index
                door_count += 1

                # Inicializar estado de la puerta como cerrada en MapManager
                is_open = door.get("is_open", False)
                if not is_open and self.map_manager:
                    self.map_manager.block_tile(map_id, x, y)
                    logger.debug("Puerta inicializada como cerrada en (%d, %d, %d)", map_id, x, y)

                logger.debug(
                    "Puerta cargada: Mapa %d (%d, %d) - GrhIndex=%d - %s - Estado: %s",
                    map_id,
                    x,
                    y,
                    grh_index,
                    door.get("name", "Sin nombre"),
                    "abierta" if is_open else "cerrada",
                )

            logger.info("✓ Cargadas %d puertas desde configuración manual", door_count)

        except Exception:
            logger.exception("Error cargando puertas manuales")
