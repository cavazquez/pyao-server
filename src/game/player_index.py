"""Índice de jugadores por mapa con manejo de ocupación de tiles."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.messaging.message_sender import MessageSender

logger = logging.getLogger(__name__)


class PlayerIndex:
    """Gestiona jugadores conectados agrupados por mapa."""

    def __init__(self, tile_occupation: dict[tuple[int, int, int], str]) -> None:
        """Inicializa el índice.

        Args:
            tile_occupation: Diccionario compartido de ocupación de tiles.
        """
        self._tile_occupation = tile_occupation
        self._players_by_map: dict[int, dict[int, tuple[MessageSender, str]]] = {}

    @property
    def players_by_map(self) -> dict[int, dict[int, tuple[MessageSender, str]]]:
        """Storage interno (compatibilidad con MapManager)."""
        return self._players_by_map

    def add_player(
        self, map_id: int, user_id: int, message_sender: MessageSender, username: str = ""
    ) -> None:
        """Agrega un jugador al mapa."""
        if map_id not in self._players_by_map:
            self._players_by_map[map_id] = {}
        self._players_by_map[map_id][user_id] = (message_sender, username)
        logger.debug("Jugador %d (%s) agregado al mapa %d", user_id, username, map_id)

    def remove_player(self, map_id: int, user_id: int) -> None:
        """Remueve un jugador del mapa y libera ocupación."""
        if map_id not in self._players_by_map or user_id not in self._players_by_map[map_id]:
            return

        keys_to_remove = [
            key
            for key, occupant in self._tile_occupation.items()
            if occupant == f"player:{user_id}" and key[0] == map_id
        ]
        for key in keys_to_remove:
            del self._tile_occupation[key]
            logger.debug("Tile (%d,%d) liberado al remover jugador %d", key[1], key[2], user_id)

        del self._players_by_map[map_id][user_id]
        logger.debug("Jugador %d removido del mapa %d", user_id, map_id)

        if not self._players_by_map[map_id]:
            del self._players_by_map[map_id]
            logger.debug("Mapa %d eliminado (sin jugadores)", map_id)

    def remove_player_from_all_maps(self, user_id: int) -> None:
        """Remueve un jugador de todos los mapas y limpia ocupación."""
        maps_to_clean: list[int] = []
        for map_id, players in self._players_by_map.items():
            if user_id not in players:
                continue
            keys_to_remove = [
                key
                for key, occupant in self._tile_occupation.items()
                if occupant == f"player:{user_id}" and key[0] == map_id
            ]
            for key in keys_to_remove:
                del self._tile_occupation[key]
                logger.debug(
                    "Tile (%d,%d) liberado al remover jugador %d del mapa %d",
                    key[1],
                    key[2],
                    user_id,
                    map_id,
                )
            del players[user_id]
            logger.debug("Jugador %d removido del mapa %d", user_id, map_id)
            if not players:
                maps_to_clean.append(map_id)

        for map_id in maps_to_clean:
            del self._players_by_map[map_id]
            logger.debug("Mapa %d eliminado (sin jugadores)", map_id)

    def get_players_in_map(self, map_id: int, exclude_user_id: int | None = None) -> list[int]:
        """Lista de user_ids en un mapa (opcionalmente excluyendo uno).

        Returns:
            list[int]: user_ids presentes en el mapa.
        """
        if map_id not in self._players_by_map:
            return []
        players = list(self._players_by_map[map_id].keys())
        if exclude_user_id is not None and exclude_user_id in players:
            players.remove(exclude_user_id)
        return players

    def get_maps_with_players(self) -> list[int]:
        """IDs de mapas con jugadores conectados.

        Returns:
            list[int]: map_ids con jugadores.
        """
        return list(self._players_by_map.keys())

    def get_player_message_sender(self, user_id: int) -> MessageSender | None:
        """MessageSender de un jugador, si está conectado.

        Returns:
            MessageSender | None: sender si el jugador está online.
        """
        for players_dict in self._players_by_map.values():
            if user_id in players_dict:
                sender, _ = players_dict[user_id]
                return sender
        return None

    def find_player_by_username(self, username: str) -> int | None:
        """Busca jugador online por username (case-insensitive).

        Returns:
            int | None: user_id encontrado o None.
        """
        username_lower = username.lower().strip()
        for players_dict in self._players_by_map.values():
            for user_id, (_sender, player_username) in players_dict.items():
                if player_username.lower().strip() == username_lower:
                    return user_id
        return None

    def get_all_online_players(self) -> list[tuple[int, str, int]]:
        """Devuelve (user_id, username, map_id) de todos los conectados.

        Returns:
            list[tuple[int, str, int]]: jugadores online con su mapa.
        """
        players: list[tuple[int, str, int]] = []
        for map_id, players_dict in self._players_by_map.items():
            for user_id, (_sender, username) in players_dict.items():
                players.append((user_id, username, map_id))
        return players

    def get_player_username(self, user_id: int) -> str | None:
        """Username de un jugador, si está conectado.

        Returns:
            str | None: username o None si no está online.
        """
        for players_dict in self._players_by_map.values():
            if user_id in players_dict:
                _, username = players_dict[user_id]
                return username
        return None

    def get_username(self, user_id: int, map_id: int | None = None) -> str | None:
        """Obtiene username, opcionalmente restringiendo a un mapa.

        Returns:
            str | None: username o None si no se encuentra.
        """
        if map_id is not None:
            if map_id not in self._players_by_map:
                return None
            player_data = self._players_by_map[map_id].get(user_id)
            return player_data[1] if player_data else None

        for players in self._players_by_map.values():
            if user_id in players:
                return players[user_id][1]
        return None

    def get_message_sender(self, user_id: int, map_id: int | None = None) -> MessageSender | None:
        """Obtiene MessageSender, opcionalmente restringiendo a un mapa.

        Returns:
            MessageSender | None: sender o None si no está.
        """
        if map_id is not None:
            if map_id not in self._players_by_map:
                return None
            player_data = self._players_by_map[map_id].get(user_id)
            return player_data[0] if player_data else None

        for players in self._players_by_map.values():
            if user_id in players:
                return players[user_id][0]
        return None

    def get_all_message_senders_in_map(
        self, map_id: int, exclude_user_id: int | None = None
    ) -> list[MessageSender]:
        """MessageSenders en un mapa, excluyendo opcionalmente un usuario.

        Returns:
            list[MessageSender]: senders presentes.
        """
        if map_id not in self._players_by_map:
            return []
        senders = []
        for user_id, (sender, _username) in self._players_by_map[map_id].items():
            if exclude_user_id is None or user_id != exclude_user_id:
                senders.append(sender)
        return senders

    def get_player_count_in_map(self, map_id: int) -> int:
        """Cantidad de jugadores en un mapa.

        Returns:
            int: total de jugadores en el mapa.
        """
        if map_id not in self._players_by_map:
            return 0
        return len(self._players_by_map[map_id])

    def get_all_connected_players(self) -> list[str]:
        """Nombres de todos los jugadores conectados (únicos).

        Returns:
            list[str]: usernames conectados.
        """
        usernames: list[str] = []
        for players in self._players_by_map.values():
            for _sender, username in players.values():
                if username and username not in usernames:
                    usernames.append(username)
        return usernames

    def get_all_connected_user_ids(self) -> list[int]:
        """user_ids de todos los jugadores conectados (únicos).

        Returns:
            list[int]: user_ids conectados.
        """
        user_ids: list[int] = []
        for players in self._players_by_map.values():
            for user_id in players:
                if user_id not in user_ids:
                    user_ids.append(user_id)
        return user_ids
