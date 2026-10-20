"""Índice de NPCs por mapa con manejo de ocupación de tiles."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.game.tile_occupation import TileOccupation
    from src.models.npc import NPC

logger = logging.getLogger(__name__)


class NpcIndex:
    """Gestiona NPCs agrupados por mapa y su ocupación de tiles."""

    def __init__(self, tile_occupation: TileOccupation) -> None:
        """Inicializa el índice.

        Args:
            tile_occupation: Diccionario compartido de ocupación de tiles
                {(map_id, x, y): "npc:<instance_id>" | "player:<user_id>"}.
        """
        self._tile_occupation = tile_occupation
        self._npcs_by_map: dict[int, dict[str, NPC]] = {}
        self._by_character: dict[tuple[int, int], NPC] = {}
        self._map_by_instance: dict[str, int] = {}
        self._character_by_instance: dict[str, int] = {}
        self._registered_position: dict[str, tuple[int, int]] = {}

    @property
    def npcs_by_map(self) -> dict[int, dict[str, NPC]]:
        """Acceso al storage interno (compatibilidad con MapManager)."""
        return self._npcs_by_map

    def add_npc(self, map_id: int, npc: NPC) -> None:
        """Agrega un NPC al mapa y marca ocupación.

        Raises:
            ValueError: Si otro actor ocupa el tile o usa ese CharIndex en el mapa.
        """
        owner = self._by_character.get((map_id, npc.char_index))
        if owner is not None and owner.instance_id != npc.instance_id:
            msg = f"CharIndex {npc.char_index} ya pertenece a {owner.instance_id} en mapa {map_id}"
            raise ValueError(msg)
        occupant = self._tile_occupation.get_occupant(map_id, npc.x, npc.y)
        if occupant is not None and occupant != f"npc:{npc.instance_id}":
            msg = f"tile ya ocupado por {occupant}"
            raise ValueError(msg)
        old_map = self._map_by_instance.get(npc.instance_id)
        if old_map is not None:
            self.remove_npc(old_map, npc.instance_id)
        if map_id not in self._npcs_by_map:
            self._npcs_by_map[map_id] = {}

        self._tile_occupation.occupy_npc(map_id, npc.x, npc.y, npc.instance_id)
        self._npcs_by_map[map_id][npc.instance_id] = npc
        self._by_character[map_id, npc.char_index] = npc
        self._map_by_instance[npc.instance_id] = map_id
        self._character_by_instance[npc.instance_id] = npc.char_index
        self._registered_position[npc.instance_id] = npc.x, npc.y
        logger.debug("NPC %s agregado al mapa %d en tile (%d,%d)", npc.name, map_id, npc.x, npc.y)

    def move_npc(
        self, map_id: int, char_index: int, old_x: int, old_y: int, new_x: int, new_y: int
    ) -> None:
        """Mueve un NPC liberando y reasignando ocupación."""
        npc = self._by_character.get((map_id, char_index))
        if npc is not None:
            self._tile_occupation.move_npc(map_id, old_x, old_y, new_x, new_y, npc.instance_id)
            npc.x, npc.y = new_x, new_y
            self._registered_position[npc.instance_id] = new_x, new_y

    def remove_npc(self, map_id: int, instance_id: str) -> None:
        """Remueve un NPC y libera su tile."""
        if map_id not in self._npcs_by_map:
            return

        npc = self._npcs_by_map[map_id].get(instance_id)
        if npc is None:
            return

        # El servicio puede haber mutado el modelo antes de volver a registrarlo.
        # También acepta movimientos que ya actualizaron TileOccupation directamente.
        positions = {self._registered_position.pop(instance_id), (npc.x, npc.y)}
        for x, y in positions:
            if self._tile_occupation.get_occupant(map_id, x, y) == f"npc:{instance_id}":
                self._tile_occupation.remove_npc(map_id, x, y)

        del self._npcs_by_map[map_id][instance_id]
        old_character = self._character_by_instance.pop(instance_id)
        self._by_character.pop((map_id, old_character), None)
        self._map_by_instance.pop(instance_id, None)
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
        return self._by_character.get((map_id, char_index))
