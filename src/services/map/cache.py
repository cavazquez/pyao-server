"""Helpers de caché para recursos de mapas.

Formato único en disco (``maps``): claves ``map_<id>``, ``signs``/``doors`` como
``[[x, y, grh], ...]``. Funciones de módulo compartidas por ``MapCacheLoader`` y tests.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, cast

logger = logging.getLogger(__name__)

MAP_RESOURCES_CACHE_VERSION = 2


def build_mtimes(files: list[Path]) -> tuple[list[str], dict[str, float]]:
    """Construye listas de nombres y mtimes para una lista de paths."""
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


def read_cache_file_strict(cache_path: Path) -> dict[str, Any]:
    """Lee el JSON; exige objeto raíz dict (como en validación estricta de caché)."""
    with cache_path.open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        msg = "Cache root is not a dict"
        raise json.JSONDecodeError(msg, doc="", pos=0)
    return data


def is_cache_source_valid_lists(
    blocked_files: list[Path],
    objects_files: list[Path],
    blocked_info: dict[str, Any],
    objects_info: dict[str, Any],
) -> bool:
    """Valida caché cuyo ``source`` almacena listas ``files`` + ``mtimes`` (tests / legado)."""
    current_blocked_names, current_blocked_mtimes = build_mtimes(blocked_files)
    current_objects_names, current_objects_mtimes = build_mtimes(objects_files)

    if blocked_info.get("files") != current_blocked_names:
        return False
    if objects_info.get("files") != current_objects_names:
        return False

    if blocked_info.get("mtimes") != current_blocked_mtimes:
        return False
    return objects_info.get("mtimes") == current_objects_mtimes


def serialize_resources_to_maps_dict(
    resources: dict[str, dict[str, set[tuple[int, int]]]],
    signs: dict[str, dict[tuple[int, int], int]],
    doors: dict[str, dict[tuple[int, int], int]],
) -> dict[str, Any]:
    """Serializa a la estructura bajo la clave ``maps`` del archivo de caché."""
    serialized: dict[str, Any] = {}
    for map_key, res in resources.items():
        serialized[map_key] = {
            "blocked": list(map(list, res.get("blocked", set()))),
            "water": list(map(list, res.get("water", set()))),
            "trees": list(map(list, res.get("trees", set()))),
            "mines": list(map(list, res.get("mines", set()))),
            "anvils": list(map(list, res.get("anvils", set()))),
            "forges": list(map(list, res.get("forges", set()))),
            "signs": [[x, y, grh] for (x, y), grh in signs.get(map_key, {}).items()],
            "doors": [[x, y, grh] for (x, y), grh in doors.get(map_key, {}).items()],
        }
    return serialized


def rebuild_resources_from_maps_data(
    maps_data: dict[str, Any],
    resources: dict[str, dict[str, set[tuple[int, int]]]],
    signs: dict[str, dict[tuple[int, int], int]],
    doors: dict[str, dict[tuple[int, int], int]],
) -> None:
    """Reconstruye dicts en memoria desde el mismo formato que guarda ``save_cache``."""
    resources.clear()
    signs.clear()
    doors.clear()

    for key, res in maps_data.items():
        if not isinstance(res, dict):
            continue
        if isinstance(key, str) and key.startswith("map_"):
            map_key = key
        elif str(key).isdigit():
            map_key = f"map_{int(key)}"
        else:
            continue

        blocked = res.get("blocked", [])
        water = res.get("water", [])
        trees = res.get("trees", [])
        mines = res.get("mines", [])
        anvils = res.get("anvils", [])
        forges = res.get("forges", [])
        signs_list = res.get("signs", [])
        doors_list = res.get("doors", [])

        resources[map_key] = {
            "blocked": {tuple(c) for c in blocked},
            "water": {tuple(c) for c in water},
            "trees": {tuple(c) for c in trees},
            "mines": {tuple(c) for c in mines},
            "anvils": {tuple(c) for c in anvils},
            "forges": {tuple(c) for c in forges},
        }

        if signs_list:
            signs[map_key] = {(s[0], s[1]): s[2] for s in signs_list}
        if doors_list:
            doors[map_key] = {(d[0], d[1]): d[2] for d in doors_list}


class MapCacheLoader:
    """Carga y guarda caché de recursos de mapas."""

    def __init__(self, maps_dir: Path, cache_dir: Path) -> None:
        """Inicializa el loader de caché.

        Args:
            maps_dir: Directorio con los JSON fuente.
            cache_dir: Directorio donde guardar/leer cachés.
        """
        self.maps_dir = maps_dir
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def try_load_from_cache(
        self,
        resources: dict[str, dict[str, set[tuple[int, int]]]],
        signs: dict[str, dict[tuple[int, int], int]],
        doors: dict[str, dict[tuple[int, int], int]],
    ) -> bool:
        """Intenta cargar caché JSON.

        Returns:
            True si carga válida, False en caso contrario.
        """
        cache_path = self.cache_dir / "map_resources_cache.json"
        start_time = time.time()
        if not cache_path.exists():
            return False

        try:
            data = self._read_cache_file(cache_path)
        except OSError, json.JSONDecodeError:
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
            rebuild_resources_from_maps_data(maps_data, resources, signs, doors)
        except Exception:
            logger.exception("Error cargando recursos de mapas desde caché")
            resources.clear()
            signs.clear()
            doors.clear()
            return False
        else:
            elapsed_time = time.time() - start_time
            logger.info(
                "✓ Recursos de mapas cargados desde caché: %s en %.3f segundos",
                cache_path,
                elapsed_time,
            )
            return True

    def save_cache(
        self,
        resources: dict[str, dict[str, set[tuple[int, int]]]],
        signs: dict[str, dict[tuple[int, int], int]],
        doors: dict[str, dict[tuple[int, int], int]],
    ) -> None:
        """Guarda caché JSON."""
        cache_path = self.cache_dir / "map_resources_cache.json"
        try:
            data = {
                "version": MAP_RESOURCES_CACHE_VERSION,
                "source": self._build_source_info(),
                "maps": serialize_resources_to_maps_dict(resources, signs, doors),
            }
            with cache_path.open("w", encoding="utf-8") as f:
                json.dump(data, f)
            logger.info("✓ Caché de recursos guardado en %s", cache_path)
        except Exception:
            logger.exception("No se pudo guardar caché en %s", cache_path)

    def _read_cache_file(self, cache_path: Path) -> dict[str, Any]:
        with cache_path.open("r", encoding="utf-8") as f:
            return cast("dict[str, Any]", json.load(f))

    def _build_source_info(self) -> dict[str, dict[str, float]]:
        return {
            "blocked": {f.name: f.stat().st_mtime for f in self.maps_dir.glob("blocked_*.json")},
            "objects": {f.name: f.stat().st_mtime for f in self.maps_dir.glob("objects_*.json")},
        }

    def _is_cache_source_valid(
        self,
        blocked_files: list[Path],
        objects_files: list[Path],
        blocked_info: dict[str, float],
        objects_info: dict[str, float],
    ) -> bool:
        return all(blocked_info.get(f.name, 0) == f.stat().st_mtime for f in blocked_files) and all(
            objects_info.get(f.name, 0) == f.stat().st_mtime for f in objects_files
        )
