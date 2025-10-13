"""Gestor de mapas y jugadores para broadcast multijugador."""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.message_sender import MessageSender

logger = logging.getLogger(__name__)


class MapManager:
    """Gestiona qué jugadores están en qué mapa para broadcast de eventos."""

    def __init__(self) -> None:
        """Inicializa el gestor de mapas.

        Estructura interna: {map_id: {user_id: (message_sender, username)}}
        """
        self._players_by_map: dict[int, dict[int, tuple[MessageSender, str]]] = {}

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

    def get_message_sender(self, map_id: int, user_id: int) -> MessageSender | None:
        """Obtiene el MessageSender de un jugador en un mapa.

        Args:
            map_id: ID del mapa.
            user_id: ID del usuario.

        Returns:
            MessageSender del jugador o None si no existe.
        """
        if map_id not in self._players_by_map:
            return None

        player_data = self._players_by_map[map_id].get(user_id)
        return player_data[0] if player_data else None

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
            for _user_id, (_sender, username) in players.items():
                if username and username not in usernames:
                    usernames.append(username)
        return usernames
