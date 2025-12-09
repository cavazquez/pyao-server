"""Índice de NPCs por mapa con manejo de ocupación de tiles."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.models.npc import NPC

logger = logging.getLogger(__name__)


class NpcIndex:
    """Gestiona NPCs agrupados por mapa y su ocupación de tiles."""

    def __init__(self, tile_occupation: dict[tuple[int, int, int], str]) -> None:
        """Inicializa el índice.

        Args:
            tile_occupation: Diccionario compartido de ocupación de tiles
                {(map_id, x, y): "npc:<instance_id>" | "player:<user_id>"}.
        """
        self._tile_occupation = tile_occupation
        self._npcs_by_map: dict[int, dict[str, NPC]] = {}

    @property
    def npcs_by_map(self) -> dict[int, dict[str, NPC]]:
        """Acceso al storage interno (compatibilidad con MapManager)."""
        return self._npcs_by_map

    def add_npc(self, map_id: int, npc: NPC) -> None:
        """Agrega un NPC al mapa y marca ocupación.

        Raises:
            ValueError: si el tile está ocupado.
        """
        if map_id not in self._npcs_by_map:
            self._npcs_by_map[map_id] = {}

        tile_key = (map_id, npc.x, npc.y)
        if tile_key in self._tile_occupation:
            occupant = self._tile_occupation[tile_key]
            msg = (
                f"No se puede agregar NPC {npc.name} en ({npc.x},{npc.y}): "
                f"tile ya ocupado por {occupant}"
            )
            raise ValueError(msg)

        self._npcs_by_map[map_id][npc.instance_id] = npc
        self._tile_occupation[tile_key] = f"npc:{npc.instance_id}"
        logger.debug("NPC %s agregado al mapa %d en tile (%d,%d)", npc.name, map_id, npc.x, npc.y)

    def move_npc(
        self, map_id: int, char_index: int, old_x: int, old_y: int, new_x: int, new_y: int
    ) -> None:
        """Mueve un NPC liberando y reasignando ocupación."""
        old_tile_key = (map_id, old_x, old_y)
        self._tile_occupation.pop(old_tile_key, None)

        if map_id not in self._npcs_by_map:
            return

        for npc in self._npcs_by_map[map_id].values():
            if getattr(npc, "char_index", None) == char_index:
                new_tile_key = (map_id, new_x, new_y)
                self._tile_occupation[new_tile_key] = f"npc:{npc.instance_id}"
                break

    def remove_npc(self, map_id: int, instance_id: str) -> None:
        """Remueve un NPC y libera su tile."""
        if map_id not in self._npcs_by_map:
            return

        npc = self._npcs_by_map[map_id].get(instance_id)
        if npc is None:
            return

        tile_key = (map_id, npc.x, npc.y)
        if tile_key in self._tile_occupation:
            del self._tile_occupation[tile_key]
            logger.debug("Tile (%d,%d) liberado al remover NPC %s", npc.x, npc.y, npc.name)

        del self._npcs_by_map[map_id][instance_id]
        logger.debug("NPC %s removido del mapa %d", npc.name, map_id)

        if not self._npcs_by_map[map_id]:
            del self._npcs_by_map[map_id]
            logger.debug("Mapa %d eliminado (sin NPCs)", map_id)

    def get_npcs_in_map(self, map_id: int) -> list[NPC]:
        """Devuelve los NPCs de un mapa.

        Returns:
            list[NPC | SimpleNamespace]: NPCs presentes en el mapa.
        """
        if map_id not in self._npcs_by_map:
            return []
        return list(self._npcs_by_map[map_id].values())

    def get_all_npcs(self) -> list[NPC]:
        """Devuelve todos los NPCs de todos los mapas.

        Returns:
            list[NPC | SimpleNamespace]: NPCs de todos los mapas.
        """
        all_npcs: list[NPC] = []
        for npcs_in_map in self._npcs_by_map.values():
            all_npcs.extend(npcs_in_map.values())
        return all_npcs

    def get_npc_by_char_index(self, map_id: int, char_index: int) -> NPC | None:
        """Busca un NPC por char_index en un mapa.

        Returns:
            NPC | SimpleNamespace | None: NPC encontrado o None si no existe.
        """
        if map_id not in self._npcs_by_map:
            return None

        for npc in self._npcs_by_map[map_id].values():
            if getattr(npc, "char_index", None) == char_index:
                return npc
        return None
