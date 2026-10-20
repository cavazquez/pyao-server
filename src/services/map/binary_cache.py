"""Caché descartable compacta de recursos con huellas de sus archivos fuente."""

from __future__ import annotations

import hashlib
import logging
import tempfile
import time
from pathlib import Path
from typing import Any

from src.game.coordinate_mask import TERRAIN_LAYERS, CoordinateMask, ResourcesMap
from src.runtime_paths import state_dir

logger = logging.getLogger(__name__)

try:
    import msgpack  # type: ignore[import-untyped]

    MSGPACK_AVAILABLE = True
except ImportError:
    MSGPACK_AVAILABLE = False

MAP_BINARY_DIR = state_dir() / "map_binary"
COMPACT_CACHE_VERSION = 1
COMPACT_CACHE_NAME = "terrain-v1.msgpack"


class MapBinaryCache:
    """Carga planos de bits directamente, sin reconstruir millones de tuplas."""

    def __init__(
        self,
        maps_dir: Path,
        resources: ResourcesMap,
        signs: dict[str, dict[tuple[int, int], int]],
        doors: dict[str, dict[tuple[int, int], int]],
    ) -> None:
        """Inicializa el manejador de caché binario."""
        self.maps_dir = maps_dir
        self.resources = resources
        self.signs = signs
        self.doors = doors

    def _source_info(self) -> dict[str, Any]:
        """Identifica contenido y directorio; dos fixtures nunca comparten datos.

        Returns:
            Ruta canónica y SHA256 de cada archivo de terreno/objetos.
        """
        files = sorted(
            [*self.maps_dir.glob("blocked_*.json"), *self.maps_dir.glob("objects_*.json")]
        )
        hashes = {}
        for path in files:
            with path.open("rb") as source:
                hashes[path.name] = hashlib.file_digest(source, "sha256").hexdigest()
        return {"directory": str(self.maps_dir.resolve()), "files": hashes}

    def try_load_from_binary(self) -> bool:
        """Carga sólo la caché compacta vigente; una caché antigua se reconstruye.

        Returns:
            Si todos los planos y las huellas de origen son válidos.
        """
        binary_file = MAP_BINARY_DIR / COMPACT_CACHE_NAME
        if not MSGPACK_AVAILABLE or not binary_file.exists():
            return False
        started = time.perf_counter()
        try:
            with binary_file.open("rb") as source:
                data = msgpack.unpack(source, raw=False)
            if not isinstance(data, dict) or (
                data.get("version") != COMPACT_CACHE_VERSION
                or data.get("source") != self._source_info()
            ):
                return False
            self._rebuild_from_binary(data)
        except OSError, ValueError, TypeError, KeyError, AttributeError:
            logger.warning("Caché compacta inválida; se reconstruirá", exc_info=True)
            return False
        logger.info(
            "✓ Recursos compactos cargados desde %s en %.3f segundos",
            binary_file,
            time.perf_counter() - started,
        )
        return True

    def generate_binary_cache(self) -> bool:
        """Guarda sólo planos compactos en un reemplazo atómico descartable.

        Returns:
            Si se guardó la caché; un fallo permite usar el fallback JSON.
        """
        if not MSGPACK_AVAILABLE:
            return False
        temporary: Path | None = None
        try:
            data = {
                "version": COMPACT_CACHE_VERSION,
                "source": self._source_info(),
                "maps": self._encoded_resources(),
                "signs": {
                    key: [[x, y, graphic] for (x, y), graphic in rows.items()]
                    for key, rows in self.signs.items()
                },
                "doors": {
                    key: [[x, y, graphic] for (x, y), graphic in rows.items()]
                    for key, rows in self.doors.items()
                },
            }
            MAP_BINARY_DIR.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                dir=MAP_BINARY_DIR, prefix=COMPACT_CACHE_NAME, delete=False
            ) as output:
                temporary = Path(output.name)
                msgpack.pack(data, output, use_bin_type=True)
            Path(temporary).replace(MAP_BINARY_DIR / COMPACT_CACHE_NAME)
        except OSError, ValueError, TypeError:
            logger.warning("No se pudo guardar la caché compacta", exc_info=True)
            return False
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        return True

    def _encoded_resources(self) -> dict[str, dict[str, bytes]]:
        result: dict[str, dict[str, bytes]] = {}
        for key, values in self.resources.items():
            result[key] = {}
            for layer in TERRAIN_LAYERS:
                current = values[layer]
                mask = current if isinstance(current, CoordinateMask) else CoordinateMask(current)
                result[key][layer] = mask.to_bytes()
        return result

    def _rebuild_from_binary(self, data: dict[str, Any]) -> None:
        resources = {
            key: {layer: CoordinateMask.from_bytes(values[layer]) for layer in TERRAIN_LAYERS}
            for key, values in data["maps"].items()
        }
        signs = {
            key: {(x, y): graphic for x, y, graphic in rows} for key, rows in data["signs"].items()
        }
        doors = {
            key: {(x, y): graphic for x, y, graphic in rows} for key, rows in data["doors"].items()
        }
        self.resources.clear()
        self.resources.update(resources)
        self.signs.clear()
        self.signs.update(signs)
        self.doors.clear()
        self.doors.update(doors)
