"""Extensión de MapManager con índice espacial para colisiones."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import cast

logger = logging.getLogger(__name__)


class SpatialIndexMixin:
    """Mixin para agregar índice espacial al MapManager."""

    def can_move_to(self, map_id: int, x: int, y: int) -> bool:
        """Verifica si se puede mover a una posición.

        Args:
            map_id: ID del mapa.
            x: Coordenada X.
            y: Coordenada Y.

        Returns:
            True si la posición está libre, False si está bloqueada u ocupada.
        """
        map_sizes = cast("dict[int, tuple[int, int]]", getattr(self, "_map_sizes", {}))
        width, height = map_sizes.get(map_id, (100, 100))

        # Verificar límites del mapa
        if x < 1 or x > width or y < 1 or y > height:
            return False

        # Verificar tiles bloqueados (paredes, agua, etc.)
        blocked_tiles = cast("dict[int, set[tuple[int, int]]]", getattr(self, "_blocked_tiles", {}))
        if map_id in blocked_tiles and (x, y) in blocked_tiles[map_id]:
            return False

        # Verificar puertas cerradas
        closed_doors = cast("dict[int, set[tuple[int, int]]]", getattr(self, "_closed_doors", {}))
        if map_id in closed_doors and (x, y) in closed_doors[map_id]:
            return False

        # Verificar si hay un jugador o NPC en esa posición
        tile_occupation = cast(
            "dict[tuple[int, int, int], str]", getattr(self, "_tile_occupation", {})
        )
        key = (map_id, x, y)
        return key not in tile_occupation

    def is_tile_occupied(self, map_id: int, x: int, y: int) -> bool:
        """Verifica si un tile está ocupado por un jugador o NPC.

        Args:
            map_id: ID del mapa.
            x: Coordenada X.
            y: Coordenada Y.

        Returns:
            True si está ocupado, False si está libre.
        """
        key = (map_id, x, y)
        return key in self._tile_occupation  # type: ignore[attr-defined]

    def get_tile_occupant(self, map_id: int, x: int, y: int) -> str | None:
        """Obtiene información sobre quién ocupa un tile.

        Args:
            map_id: ID del mapa.
            x: Coordenada X.
            y: Coordenada Y.

        Returns:
            String con formato 'player:user_id' o 'npc:instance_id', o None si está libre.
        """
        tile_occupation = cast(
            "dict[tuple[int, int, int], str]", getattr(self, "_tile_occupation", {})
        )
        key = (map_id, x, y)
        return tile_occupation.get(key)

    def get_tile_block_reason(self, map_id: int, x: int, y: int) -> str | None:
        """Retorna la razón por la que un tile está bloqueado.

        Args:
            map_id: ID del mapa.
            x: Coordenada X.
            y: Coordenada Y.

        Returns:
            Cadena describiendo la causa del bloqueo o ``None`` si el tile está libre.
        """
        map_sizes = cast("dict[int, tuple[int, int]]", getattr(self, "_map_sizes", {}))
        width, height = map_sizes.get(map_id, (100, 100))
        if x < 1 or x > width or y < 1 or y > height:
            return "fuera de límites del mapa"

        blocked_tiles = cast("dict[int, set[tuple[int, int]]]", getattr(self, "_blocked_tiles", {}))
        if map_id in blocked_tiles and (x, y) in blocked_tiles[map_id]:
            return "tile bloqueado del mapa (map_data)"

        tile_occupation = cast(
            "dict[tuple[int, int, int], str]", getattr(self, "_tile_occupation", {})
        )
        occupant = tile_occupation.get((map_id, x, y))
        if occupant:
            if occupant.startswith("player:"):
                return f"ocupado por jugador {occupant.split(':', 1)[1]}"
            if occupant.startswith("npc:"):
                return f"ocupado por NPC {occupant.split(':', 1)[1]}"
            return f"ocupado ({occupant})"

        return None

    def update_player_tile(
        self, user_id: int, map_id: int, old_x: int, old_y: int, new_x: int, new_y: int
    ) -> None:
        """Actualiza la posición de un jugador en el índice espacial.

        Args:
            user_id: ID del jugador.
            map_id: ID del mapa.
            old_x: Coordenada X anterior.
            old_y: Coordenada Y anterior.
            new_x: Nueva coordenada X.
            new_y: Nueva coordenada Y.
        """
        # Limpiar posición anterior
        old_key = (map_id, old_x, old_y)
        if old_key in self._tile_occupation:  # type: ignore[attr-defined]
            del self._tile_occupation[old_key]  # type: ignore[attr-defined]

        # Marcar nueva posición
        new_key = (map_id, new_x, new_y)
        self._tile_occupation[new_key] = f"player:{user_id}"  # type: ignore[attr-defined]

    def update_npc_tile(
        self, instance_id: str, map_id: int, old_x: int, old_y: int, new_x: int, new_y: int
    ) -> None:
        """Actualiza la posición de un NPC en el índice espacial.

        Args:
            instance_id: ID de instancia del NPC.
            map_id: ID del mapa.
            old_x: Coordenada X anterior.
            old_y: Coordenada Y anterior.
            new_x: Nueva coordenada X.
            new_y: Nueva coordenada Y.
        """
        # Limpiar posición anterior
        old_key = (map_id, old_x, old_y)
        if old_key in self._tile_occupation:  # type: ignore[attr-defined]
            del self._tile_occupation[old_key]  # type: ignore[attr-defined]

        # Marcar nueva posición
        new_key = (map_id, new_x, new_y)
        self._tile_occupation[new_key] = f"npc:{instance_id}"  # type: ignore[attr-defined]

    def load_map_data(self, map_id: int, map_file: str | Path) -> None:
        """Carga datos de un mapa desde archivo JSON.

        Args:
            map_id: ID del mapa.
            map_file: Ruta al archivo JSON del mapa.
        """
        try:
            with Path(map_file).open(encoding="utf-8") as f:
                data = json.load(f)

            # Cargar tiles bloqueados
            blocked: set[tuple[int, int]] = set()
            blocked.update((tile["x"], tile["y"]) for tile in data.get("blocked_tiles", []))

            self._blocked_tiles[map_id] = blocked  # type: ignore[attr-defined]
            logger.info("Mapa %d cargado: %d tiles bloqueados", map_id, len(blocked))

        except FileNotFoundError:
            logger.warning("Archivo de mapa no encontrado: %s", map_file)
        except json.JSONDecodeError:
            logger.exception("Error parseando archivo de mapa: %s", map_file)
