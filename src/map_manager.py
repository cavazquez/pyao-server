"""Gestor de mapas y jugadores para broadcast multijugador."""

import logging
from typing import TYPE_CHECKING

from src.map_manager_spatial import SpatialIndexMixin

if TYPE_CHECKING:
    from src.message_sender import MessageSender
    from src.npc import NPC


logger = logging.getLogger(__name__)


class MapManager(SpatialIndexMixin):
    """Gestiona qué jugadores y NPCs están en qué mapa para broadcast de eventos."""

    def __init__(self) -> None:
        """Inicializa el gestor de mapas.

        Estructura interna:
        - _players_by_map: {map_id: {user_id: (message_sender, username)}}
        - _npcs_by_map: {map_id: {instance_id: NPC}}
        """
        self._players_by_map: dict[int, dict[int, tuple[MessageSender, str]]] = {}
        self._npcs_by_map: dict[int, dict[str, NPC]] = {}

        # Índice espacial para colisiones
        self._tile_occupation: dict[tuple[int, int, int], str] = {}

        # Tiles bloqueados por mapa (paredes, agua, etc.)
        self._blocked_tiles: dict[int, set[tuple[int, int]]] = {}

    def add_player(
        self, map_id: int, user_id: int, message_sender: MessageSender, username: str = ""
    ) -> None:
        """Agrega un jugador a un mapa.

        Args:
            map_id: ID del mapa.
            user_id: ID del usuario.
            message_sender: MessageSender del jugador.
            username: Nombre del usuario (opcional).
        """
        if map_id not in self._players_by_map:
            self._players_by_map[map_id] = {}

        self._players_by_map[map_id][user_id] = (message_sender, username)
        logger.debug("Jugador %d (%s) agregado al mapa %d", user_id, username, map_id)

    def remove_player(self, map_id: int, user_id: int) -> None:
        """Remueve un jugador de un mapa.

        Args:
            map_id: ID del mapa.
            user_id: ID del usuario.
        """
        if map_id in self._players_by_map and user_id in self._players_by_map[map_id]:
            del self._players_by_map[map_id][user_id]
            logger.debug("Jugador %d removido del mapa %d", user_id, map_id)

            # Limpiar mapa vacío
            if not self._players_by_map[map_id]:
                del self._players_by_map[map_id]
                logger.debug("Mapa %d eliminado (sin jugadores)", map_id)

    def get_players_in_map(self, map_id: int, exclude_user_id: int | None = None) -> list[int]:
        """Obtiene la lista de user_ids en un mapa.

        Args:
            map_id: ID del mapa.
            exclude_user_id: ID de usuario a excluir (opcional).

        Returns:
            Lista de user_ids en el mapa.
        """
        if map_id not in self._players_by_map:
            return []

        players = list(self._players_by_map[map_id].keys())

        if exclude_user_id is not None and exclude_user_id in players:
            players.remove(exclude_user_id)

        return players

    def get_message_sender(self, user_id: int, map_id: int | None = None) -> MessageSender | None:
        """Obtiene el MessageSender de un jugador.

        Args:
            user_id: ID del usuario.
            map_id: ID del mapa (opcional, si no se provee busca en todos los mapas).

        Returns:
            MessageSender del jugador o None si no existe.
        """
        # Si se especifica un mapa, buscar solo en ese mapa
        if map_id is not None:
            if map_id not in self._players_by_map:
                return None
            player_data = self._players_by_map[map_id].get(user_id)
            return player_data[0] if player_data else None

        # Si no se especifica mapa, buscar en todos los mapas
        for players in self._players_by_map.values():
            if user_id in players:
                return players[user_id][0]

        return None

    def get_all_message_senders_in_map(
        self, map_id: int, exclude_user_id: int | None = None
    ) -> list[MessageSender]:
        """Obtiene todos los MessageSenders de un mapa.

        Args:
            map_id: ID del mapa.
            exclude_user_id: ID de usuario a excluir (opcional).

        Returns:
            Lista de MessageSenders en el mapa.
        """
        if map_id not in self._players_by_map:
            return []

        senders = []
        for user_id, (sender, _username) in self._players_by_map[map_id].items():
            if exclude_user_id is None or user_id != exclude_user_id:
                senders.append(sender)

        return senders

    def get_player_count_in_map(self, map_id: int) -> int:
        """Obtiene el número de jugadores en un mapa.

        Args:
            map_id: ID del mapa.

        Returns:
            Número de jugadores en el mapa.
        """
        if map_id not in self._players_by_map:
            return 0

        return len(self._players_by_map[map_id])

    def remove_player_from_all_maps(self, user_id: int) -> None:
        """Remueve un jugador de todos los mapas.

        Args:
            user_id: ID del usuario.
        """
        maps_to_clean = []

        for map_id, players in self._players_by_map.items():
            if user_id in players:
                del players[user_id]
                logger.debug("Jugador %d removido del mapa %d", user_id, map_id)

                if not players:
                    maps_to_clean.append(map_id)

        # Limpiar mapas vacíos
        for map_id in maps_to_clean:
            del self._players_by_map[map_id]
            logger.debug("Mapa %d eliminado (sin jugadores)", map_id)

    def get_all_connected_players(self) -> list[str]:
        """Obtiene la lista de nombres de todos los jugadores conectados.

        Returns:
            Lista de nombres de usuario conectados.
        """
        usernames = []
        for players in self._players_by_map.values():
            for _sender, username in players.values():
                if username and username not in usernames:
                    usernames.append(username)
        return usernames

    def get_all_connected_user_ids(self) -> list[int]:
        """Obtiene la lista de user_ids de todos los jugadores conectados.

        Returns:
            Lista de user_ids conectados.
        """
        user_ids = []
        for players in self._players_by_map.values():
            for user_id in players:
                if user_id not in user_ids:
                    user_ids.append(user_id)
        return user_ids

    # Métodos para NPCs
    def add_npc(self, map_id: int, npc: NPC) -> None:
        """Agrega un NPC a un mapa.

        Args:
            map_id: ID del mapa.
            npc: Instancia del NPC.
        """
        if map_id not in self._npcs_by_map:
            self._npcs_by_map[map_id] = {}

        self._npcs_by_map[map_id][npc.instance_id] = npc
        logger.debug("NPC %s agregado al mapa %d", npc.name, map_id)

    def remove_npc(self, map_id: int, instance_id: str) -> None:
        """Remueve un NPC de un mapa.

        Args:
            map_id: ID del mapa.
            instance_id: ID único de la instancia del NPC.
        """
        if map_id in self._npcs_by_map and instance_id in self._npcs_by_map[map_id]:
            npc_name = self._npcs_by_map[map_id][instance_id].name
            del self._npcs_by_map[map_id][instance_id]
            logger.debug("NPC %s removido del mapa %d", npc_name, map_id)

            # Limpiar mapa vacío
            if not self._npcs_by_map[map_id]:
                del self._npcs_by_map[map_id]
                logger.debug("Mapa %d eliminado (sin NPCs)", map_id)

    def get_npcs_in_map(self, map_id: int) -> list[NPC]:
        """Obtiene todos los NPCs de un mapa.

        Args:
            map_id: ID del mapa.

        Returns:
            Lista de NPCs en el mapa.
        """
        if map_id not in self._npcs_by_map:
            return []

        return list(self._npcs_by_map[map_id].values())

    def get_npc_by_char_index(self, map_id: int, char_index: int) -> NPC | None:
        """Obtiene un NPC por su CharIndex en un mapa.

        Args:
            map_id: ID del mapa.
            char_index: CharIndex del NPC.

        Returns:
            Instancia del NPC o None si no existe.
        """
        if map_id not in self._npcs_by_map:
            return None

        for npc in self._npcs_by_map[map_id].values():
            if npc.char_index == char_index:
                return npc

        return None

    def get_all_npcs(self) -> list[NPC]:
        """Obtiene todos los NPCs del mundo.

        Returns:
            Lista de todos los NPCs.
        """
        npcs: list[NPC] = []
        for map_npcs in self._npcs_by_map.values():
            npcs.extend(map_npcs.values())
        return npcs
