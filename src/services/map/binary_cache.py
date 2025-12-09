"""Helpers para caché binario de recursos de mapas (MessagePack)."""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

try:
    import msgpack  # type: ignore[import-untyped]

    MSGPACK_AVAILABLE = True
except ImportError:
    MSGPACK_AVAILABLE = False

MAP_BINARY_DIR = Path("map_binary")


class MapBinaryCache:
    """Carga y genera caché binario de recursos de mapas."""

    def __init__(
        self,
        maps_dir: Path,
        resources: dict[str, dict[str, set[tuple[int, int]]]],
        signs: dict[str, dict[tuple[int, int], int]],
        doors: dict[str, dict[tuple[int, int], int]],
    ) -> None:
        """Inicializa el manejador de caché binario."""
        self.maps_dir = maps_dir
        self.resources = resources
        self.signs = signs
        self.doors = doors

    def try_load_from_binary(self) -> bool:
        """Intenta cargar recursos desde binario.

        Returns:
            True si carga binario válida, False si no.
        """
        if not MSGPACK_AVAILABLE:
            return False
        binary_file = MAP_BINARY_DIR / "maps.msgpack"
        if not binary_file.exists():
            return False

        start_time = time.time()
        try:
            with binary_file.open("rb") as f:
                data = msgpack.unpack(f, raw=False)

            self._rebuild_from_binary(data)

            elapsed_time = time.time() - start_time
            logger.info(
                "✓ Recursos de mapas cargados desde binario: %s en %.3f segundos",
                binary_file,
                elapsed_time,
            )
        except Exception:
            logger.exception("Error cargando mapas desde binario")
            self.resources.clear()
            self.signs.clear()
            self.doors.clear()
            return False
        else:
            return True

    def generate_binary_cache(self) -> None:
        """Genera caché binario llamando a la herramienta existente."""
        if not MSGPACK_AVAILABLE:
            logger.debug("msgpack no disponible; se omite binario")
            return
        try:
            from tools.compression.map_binary import convert_json_to_binary  # noqa: PLC0415

            logger.info("Generando caché binario de mapas (esto solo ocurre una vez)...")
            start_time = time.time()

            success = convert_json_to_binary(
                map_data_dir=self.maps_dir,
                map_binary_dir=MAP_BINARY_DIR,
            )

            if success:
                elapsed = time.time() - start_time
                logger.info("✓ Caché binario generado en %.2f segundos.", elapsed)
            else:
                logger.warning("No se pudo generar caché binario")
        except ImportError:
            logger.debug("tools.compression.map_binary no disponible")
        except OSError:
            logger.warning("Error generando caché binario", exc_info=True)

    def _rebuild_from_binary(self, data: dict[str, Any]) -> None:
        self.resources.clear()
        self.signs.clear()
        self.doors.clear()

        for map_id_str, coords in data.get("blocked", {}).items():
            map_id = int(map_id_str)
            map_key = f"map_{map_id}"
            if map_key not in self.resources:
                self.resources[map_key] = {
                    "blocked": set(),
                    "water": set(),
                    "trees": set(),
                    "mines": set(),
                    "anvils": set(),
                    "forges": set(),
                }
            self.resources[map_key]["blocked"] = {tuple(c) for c in coords}

        for key, res_field in [
            ("water", "water"),
            ("trees", "trees"),
            ("mines", "mines"),
            ("anvils", "anvils"),
            ("forges", "forges"),
        ]:
            for map_id_str, coords in data.get(key, {}).items():
                map_key = f"map_{int(map_id_str)}"
                if map_key in self.resources:
                    self.resources[map_key][res_field] = {tuple(c) for c in coords}

        for map_id_str, sign_list in data.get("signs", {}).items():
            map_key = f"map_{int(map_id_str)}"
            self.signs[map_key] = {(s[0], s[1]): s[2] for s in sign_list}

        for map_id_str, door_list in data.get("doors", {}).items():
            map_key = f"map_{int(map_id_str)}"
            self.doors[map_key] = {(d[0], d[1]): d[2] for d in door_list}
