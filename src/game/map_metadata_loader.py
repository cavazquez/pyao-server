"""Loader de metadatos de mapas (bloqueados, exits y transiciones)."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class MapMetadataResult:
    """Resultado de la carga de metadatos de un mapa."""

    width: int
    height: int
    blocked_tiles: set[tuple[int, int]]
    exit_tiles: dict[tuple[int, int, int], dict[str, int]]
    exit_count: int


class MapMetadataLoader:
    """Carga metadatos, tiles bloqueados y transiciones de mapas."""

    def __init__(
        self,
        map_ranges: tuple[int, int, int, int, int],
        max_map_id: int,
        max_coordinate: int,
    ) -> None:
        """Inicializa el loader con rangos y límites de validación."""
        self._map_ranges = map_ranges
        self._max_map_id = max_map_id
        self._max_coordinate = max_coordinate

        self._transitions_cache: dict[Path, object] = {}
        self._missing_transitions_files: set[Path] = set()

        self._blocked_cache: dict[Path, dict[int, list[dict[str, object]]]] = {}
        self._missing_blocked_files: set[Path] = set()

    def load_map_data(self, map_id: int, metadata_path: str | Path) -> MapMetadataResult:
        """Carga metadatos y tiles bloqueados de un mapa.

        Returns:
            MapMetadataResult: Ancho, alto, tiles bloqueados, exits y total de exits.
        """
        metadata_path = Path(metadata_path)
        blocked_path = self._blocked_file_for_map(map_id, metadata_path)

        try:
            width, height, blocked_tiles = self._load_metadata_file(metadata_path)

            if blocked_tiles is None:
                blocked_tiles = self._get_blocked_tiles_for_map(map_id, blocked_path)
                if blocked_tiles is None:
                    return MapMetadataResult(width, height, set(), {}, 0)

            blocked_set, exit_count, exit_tiles = self._build_blocked_data(map_id, blocked_tiles)
            transitions_loaded = self._load_map_transitions(
                map_id, metadata_path.parent / self._transitions_file_for_map(map_id), exit_tiles
            )

            return MapMetadataResult(
                width=width,
                height=height,
                blocked_tiles=blocked_set,
                exit_tiles=exit_tiles,
                exit_count=exit_count + transitions_loaded,
            )

        except (OSError, json.JSONDecodeError):
            logger.exception("Error cargando mapa %d desde %s", map_id, metadata_path)
            return MapMetadataResult(
                width=100, height=100, blocked_tiles=set(), exit_tiles={}, exit_count=0
            )

    # Métodos públicos para soporte y compatibilidad
    def load_metadata_file(
        self, metadata_path: Path
    ) -> tuple[int, int, list[dict[str, object]] | None]:
        """Lee archivo de metadata (versión pública).

        Returns:
            tuple[int, int, list[dict[str, object]] | None]: width, height y tiles opcionales.
        """
        return self._load_metadata_file(metadata_path)

    def load_blocked_file(self, blocked_path: Path) -> list[dict[str, object]] | None:
        """Lee archivo de tiles bloqueados (versión pública).

        Returns:
            list[dict[str, object]] | None: Tiles leídos o None si falta archivo.
        """
        return self._load_blocked_file(blocked_path)

    def get_blocked_tiles_for_map(
        self, map_id: int, blocked_path: Path
    ) -> list[dict[str, object]] | None:
        """Obtiene tiles bloqueados para el mapa (versión pública).

        Returns:
            list[dict[str, object]] | None: Tiles del mapa o None si no hay datos.
        """
        return self._get_blocked_tiles_for_map(map_id, blocked_path)

    def load_map_transitions(
        self,
        map_id: int,
        transitions_path: Path,
        exit_tiles: dict[tuple[int, int, int], dict[str, int]],
    ) -> int:
        """Carga transiciones en el mapping entregado (versión pública).

        Returns:
            int: Cantidad de transiciones cargadas.
        """
        return self._load_map_transitions(map_id, transitions_path, exit_tiles)

    @staticmethod
    def build_blocked_data(
        map_id: int, blocked_tiles: list[dict[str, object]]
    ) -> tuple[set[tuple[int, int]], int, dict[tuple[int, int, int], dict[str, int]]]:
        """Procesa tiles bloqueados (versión pública).

        Returns:
            tuple[set[tuple[int, int]], int, dict[tuple[int, int, int], dict[str, int]]]:
            tiles bloqueados, cantidad de exits y mapping de exits.
        """
        return MapMetadataLoader._build_blocked_data(map_id, blocked_tiles)

    @staticmethod
    def coerce_int(value: object) -> int | None:
        """Convierte a int (versión pública).

        Returns:
            int | None: Entero convertido o None.
        """
        return MapMetadataLoader._coerce_int(value)

    @property
    def missing_transitions_files(self) -> set[Path]:
        """Archivos de transiciones ausentes (caché pública)."""
        return self._missing_transitions_files

    @staticmethod
    def load_metadata_file_static(
        metadata_path: Path,
    ) -> tuple[int, int, list[dict[str, object]] | None]:
        """Versión estática de lectura de metadata.

        Returns:
            tuple[int, int, list[dict[str, object]] | None]: width, height y tiles opcionales.
        """
        return MapMetadataLoader._load_metadata_file(metadata_path)

    @staticmethod
    def load_blocked_file_static(blocked_path: Path) -> list[dict[str, object]] | None:
        """Versión estática de lectura de bloqueados.

        Returns:
            list[dict[str, object]] | None: Tiles leídos o None si falta archivo.
        """
        return MapMetadataLoader._load_blocked_file(blocked_path)

    def _blocked_file_for_map(self, map_id: int, metadata_path: Path) -> Path:
        if "_" in metadata_path.stem:
            if map_id <= self._map_ranges[0]:
                blocked_name = "blocked_001-050.json"
            elif map_id <= self._map_ranges[1]:
                blocked_name = "blocked_051-100.json"
            elif map_id <= self._map_ranges[2]:
                blocked_name = "blocked_101-150.json"
            elif map_id <= self._map_ranges[3]:
                blocked_name = "blocked_151-200.json"
            elif map_id <= self._map_ranges[4]:
                blocked_name = "blocked_201-250.json"
            else:
                blocked_name = "blocked_251-290.json"
            return metadata_path.with_name(blocked_name)
        return metadata_path.with_name("blocked.json")

    def _transitions_file_for_map(self, map_id: int) -> str:
        if map_id <= self._map_ranges[0]:
            return "transitions_001-050.json"
        if map_id <= self._map_ranges[1]:
            return "transitions_051-100.json"
        if map_id <= self._map_ranges[2]:
            return "transitions_101-150.json"
        if map_id <= self._map_ranges[3]:
            return "transitions_151-200.json"
        if map_id <= self._map_ranges[4]:
            return "transitions_201-250.json"
        return "transitions_251-290.json"

    @staticmethod
    def _coerce_int(value: object) -> int | None:
        """Convierte un valor a int devolviendo None si no es posible.

        Returns:
            int | None: Entero convertido o None si no es numérico.
        """
        if isinstance(value, bool) or value is None:
            return None
        if isinstance(value, (int, float)):
            return int(value)
        if isinstance(value, str):
            value = value.strip()
            if not value:
                return None
            try:
                return int(value)
            except ValueError:
                return None
        return None

    @staticmethod
    def _load_metadata_file(metadata_path: Path) -> tuple[int, int, list[dict[str, object]] | None]:
        """Lee el archivo de metadatos devolviendo tamaño y bloqueados embebidos.

        Returns:
            tuple[int, int, list[dict[str, object]] | None]: width, height y tiles opcionales.
        """
        width = 100
        height = 100
        blocked_tiles: list[dict[str, object]] | None = None

        if metadata_path.exists():  # noqa: PLR1702
            with metadata_path.open("r", encoding="utf-8") as f:
                try:
                    metadata = json.load(f)
                    if isinstance(metadata, list):
                        if len(metadata) > 0:
                            first_map = metadata[0]
                            width = int(first_map.get("w", width))
                            height = int(first_map.get("h", height))
                    else:
                        width = int(metadata.get("w", metadata.get("width", width)))
                        height = int(metadata.get("h", metadata.get("height", height)))

                    if "blocked_tiles" in metadata:
                        raw_blocked = metadata.get("blocked_tiles")
                        if isinstance(raw_blocked, list):
                            blocked_tiles = [tile for tile in raw_blocked if isinstance(tile, dict)]
                        else:
                            blocked_tiles = []

                except json.JSONDecodeError:
                    f.seek(0)
                    maps_metadata = []
                    for line_number, line in enumerate(f, start=1):
                        stripped = line.strip()
                        if not stripped:
                            continue
                        try:
                            parsed_line = json.loads(stripped)
                            if isinstance(parsed_line, dict):
                                maps_metadata.append(parsed_line)
                        except json.JSONDecodeError:
                            logger.warning(
                                "Formato inválido en %s línea %d: %s",
                                metadata_path,
                                line_number,
                                stripped[:100],
                            )
                            continue

                    if maps_metadata:
                        first_map = maps_metadata[0]
                        width = int(first_map.get("w", width))
                        height = int(first_map.get("h", height))
        else:
            logger.warning("Metadata de mapa no encontrada: %s", metadata_path)

        return width, height, blocked_tiles

    @staticmethod
    def _load_blocked_file(blocked_path: Path) -> list[dict[str, object]] | None:
        """Obtiene los tiles bloqueados desde un archivo dedicado.

        Returns:
            list[dict[str, object]] | None: Tiles leídos o None si falta el archivo.
        """
        if not blocked_path.exists():
            logger.warning("Archivo de tiles bloqueados no encontrado: %s", blocked_path)
            return None

        with blocked_path.open("r", encoding="utf-8") as f:
            try:
                raw_blocked = json.load(f)
            except json.JSONDecodeError:
                f.seek(0)
                ndjson_tiles: list[dict[str, object]] = []
                for line_number, line in enumerate(f, start=1):
                    stripped = line.strip()
                    if not stripped:
                        continue
                    try:
                        parsed_line = json.loads(stripped)
                    except json.JSONDecodeError:
                        logger.warning(
                            "Formato inválido en %s línea %d: %s",
                            blocked_path,
                            line_number,
                            stripped[:100],
                        )
                        continue
                    if isinstance(parsed_line, dict):
                        ndjson_tiles.append(parsed_line)
                raw_blocked = ndjson_tiles

        if isinstance(raw_blocked, list):
            return [tile for tile in raw_blocked if isinstance(tile, dict)]

        return []

    def _get_blocked_tiles_for_map(
        self, map_id: int, blocked_path: Path
    ) -> list[dict[str, object]] | None:
        """Obtiene tiles bloqueados para un mapa usando caché por archivo.

        Returns:
            list[dict[str, object]] | None: Tiles del mapa o None si no hay datos.
        """
        if blocked_path in self._missing_blocked_files:
            return None

        file_cache = self._blocked_cache.get(blocked_path)

        if file_cache is None:
            raw_blocked = self._load_blocked_file(blocked_path)
            if raw_blocked is None:
                self._missing_blocked_files.add(blocked_path)
                return None

            file_cache = {}
            for tile in raw_blocked:
                tile_map_id = self._coerce_int(tile.get("m"))
                if tile_map_id is None:
                    continue
                file_cache.setdefault(tile_map_id, []).append(tile)

            self._blocked_cache[blocked_path] = file_cache

        return file_cache.get(map_id, [])

    def _read_transitions_data(self, transitions_path: Path) -> object | None:
        """Lee y cachea datos de transiciones desde disco.

        Returns:
            object | None: Datos parseados o None si no hay transiciones válidas.
        """
        if transitions_path in self._missing_transitions_files:
            return None

        data = self._transitions_cache.get(transitions_path)
        if data is not None:
            logger.debug("Reutilizando transiciones en caché desde %s", transitions_path)
            return data

        if not transitions_path.exists():
            logger.debug("Archivo de transiciones no encontrado: %s", transitions_path)
            self._missing_transitions_files.add(transitions_path)
            return None

        try:
            raw_text = transitions_path.read_text(encoding="utf-8")
        except OSError:
            logger.warning("No se pudieron cargar transiciones desde %s", transitions_path)
            self._missing_transitions_files.add(transitions_path)
            return None

        try:
            data = json.loads(raw_text)
        except json.JSONDecodeError:
            groups: list[dict[str, object]] = []
            for line in raw_text.splitlines():
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    obj = json.loads(stripped)
                except json.JSONDecodeError:
                    continue
                if isinstance(obj, dict):
                    groups.append(obj)

            if not groups:
                logger.warning("No se encontraron transiciones válidas en %s", transitions_path)
                self._missing_transitions_files.add(transitions_path)
                return None

            data = groups

        self._transitions_cache[transitions_path] = data
        return data

    def _load_map_transitions(
        self,
        map_id: int,
        transitions_path: Path,
        exit_tiles: dict[tuple[int, int, int], dict[str, int]],
    ) -> int:
        """Carga transiciones de mapa desde un archivo JSON en exit_tiles existente.

        Returns:
            int: Cantidad de transiciones cargadas.
        """
        data = self._read_transitions_data(transitions_path)
        if data is None:
            return 0

        if isinstance(data, dict):
            raw_groups = data.get("transitions", [])
            transition_groups = (
                [g for g in raw_groups if isinstance(g, dict)]
                if isinstance(raw_groups, list)
                else []
            )
        elif isinstance(data, list):
            transition_groups = [g for g in data if isinstance(g, dict)]
        else:
            transition_groups = []

        transitions_loaded = 0
        for transition_group in transition_groups:
            if transition_group.get("from_map") != map_id:
                continue

            for exit_data in transition_group.get("exits", []):
                x = self._coerce_int(exit_data.get("x"))
                y = self._coerce_int(exit_data.get("y"))
                to_map = self._coerce_int(exit_data.get("to_map"))
                to_x = self._coerce_int(exit_data.get("to_x"))
                to_y = self._coerce_int(exit_data.get("to_y"))

                if (
                    x is not None
                    and y is not None
                    and to_map
                    and to_x is not None
                    and to_y is not None
                ):
                    if (
                        1 <= to_map <= self._max_map_id
                        and 1 <= to_x <= self._max_coordinate
                        and 1 <= to_y <= self._max_coordinate
                    ):
                        exit_tiles[map_id, x, y] = {
                            "to_map": to_map,
                            "to_x": to_x,
                            "to_y": to_y,
                        }
                        transitions_loaded += 1
                    else:
                        logger.debug(
                            "Transición inválida ignorada: Mapa %d (%d,%d) -> Mapa %d (%d,%d)",
                            map_id,
                            x,
                            y,
                            to_map,
                            to_x,
                            to_y,
                        )

        if transitions_loaded:
            logger.info("Transiciones cargadas para mapa %d: %d", map_id, transitions_loaded)

        return transitions_loaded

    @staticmethod
    def _build_blocked_data(
        map_id: int, blocked_tiles: list[dict[str, object]]
    ) -> tuple[set[tuple[int, int]], int, dict[tuple[int, int, int], dict[str, int]]]:
        """Procesa tiles bloqueados generando sets y salidas.

        Returns:
            tuple[set[tuple[int, int]], int, dict[tuple[int, int, int], dict[str, int]]]:
            tiles bloqueados, cantidad de exits y mapping de exits.
        """
        blocked_set: set[tuple[int, int]] = set()
        exit_tiles: dict[tuple[int, int, int], dict[str, int]] = {}
        exit_count = 0

        for tile in blocked_tiles:
            tile_map_id = MapMetadataLoader._coerce_int(tile.get("m"))
            if tile_map_id is not None and tile_map_id != map_id:
                continue

            tile_type = tile.get("t", tile.get("type"))
            x = MapMetadataLoader._coerce_int(tile.get("x"))
            y = MapMetadataLoader._coerce_int(tile.get("y"))
            if x is None or y is None:
                continue

            if tile_type == "exit":
                to_map = MapMetadataLoader._coerce_int(tile.get("to_map"))
                to_x = MapMetadataLoader._coerce_int(tile.get("to_x"))
                to_y = MapMetadataLoader._coerce_int(tile.get("to_y"))

                if to_map and to_x is not None and to_y is not None and to_map > 0:
                    exit_tiles[map_id, x, y] = {
                        "to_map": to_map,
                        "to_x": to_x,
                        "to_y": to_y,
                    }
                    exit_count += 1

            blocked_set.add((x, y))

        return blocked_set, exit_count, exit_tiles
