"""Índice de jugadores por mapa con manejo de ocupación de tiles."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.game.tile_occupation import TileOccupation
    from src.messaging.message_sender import MessageSender

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class _OnlinePlayer:
    """La sesión pertenece al usuario; la pertenencia a mapas puede transicionar."""

    sender: MessageSender
    username: str
    maps: set[int] = field(default_factory=set)


class PlayerIndex:
    """Gestiona jugadores conectados agrupados por mapa."""

    def __init__(self, tile_occupation: TileOccupation) -> None:
        """Inicializa el índice.

        Args:
            tile_occupation: Diccionario compartido de ocupación de tiles.
        """
        self._tile_occupation = tile_occupation
        self._players_by_map: dict[int, dict[int, tuple[MessageSender, str]]] = {}
        self._players_by_id: dict[int, _OnlinePlayer] = {}
        self._players_by_name: dict[str, dict[int, _OnlinePlayer]] = {}

    @staticmethod
    def _normalized_name(username: str) -> str:
        return username.lower().strip()

    def _forget_name(self, user_id: int, username: str) -> None:
        key = self._normalized_name(username)
        entries = self._players_by_name.get(key)
        if entries is not None:
            entries.pop(user_id, None)
            if not entries:
                del self._players_by_name[key]

    @property
    def players_by_map(self) -> dict[int, dict[int, tuple[MessageSender, str]]]:
        """Storage interno (compatibilidad con MapManager)."""
        return self._players_by_map

    def add_player(
        self, map_id: int, user_id: int, message_sender: MessageSender, username: str = ""
    ) -> None:
        """Agrega un jugador al mapa."""
        session = self._players_by_id.get(user_id)
        if session is not None and session.sender is not message_sender:
            # Una reconexión reemplaza la sesión completa, no sólo una ubicación.
            self.remove_player_from_all_maps(user_id)
            session = None
        if session is None:
            session = _OnlinePlayer(message_sender, username)
            self._players_by_id[user_id] = session
        elif session.username != username:
            self._forget_name(user_id, session.username)
            session.username = username
            for previous_map in session.maps:
                self._players_by_map[previous_map][user_id] = (message_sender, username)
        session.maps.add(map_id)
        self._players_by_name.setdefault(self._normalized_name(username), {})[user_id] = session
        if map_id not in self._players_by_map:
            self._players_by_map[map_id] = {}
        self._players_by_map[map_id][user_id] = (message_sender, username)
        logger.debug("Jugador %d (%s) agregado al mapa %d", user_id, username, map_id)

    def remove_player(
        self, map_id: int, user_id: int, expected_sender: MessageSender | None = None
    ) -> None:
        """Remueve un jugador del mapa y libera ocupación."""
        if map_id not in self._players_by_map or user_id not in self._players_by_map[map_id]:
            return
        if (
            expected_sender is not None
            and self._players_by_map[map_id][user_id][0] is not expected_sender
        ):
            return

        self._tile_occupation.remove_player(user_id, map_id)
        logger.debug("Tiles liberados para jugador %d en mapa %d", user_id, map_id)

        del self._players_by_map[map_id][user_id]
        session = self._players_by_id[user_id]
        session.maps.discard(map_id)
        if not session.maps:
            self._players_by_id.pop(user_id)
            self._forget_name(user_id, session.username)
        logger.debug("Jugador %d removido del mapa %d", user_id, map_id)

        if not self._players_by_map[map_id]:
            del self._players_by_map[map_id]
            logger.debug("Mapa %d eliminado (sin jugadores)", map_id)

    def remove_player_from_all_maps(
        self, user_id: int, expected_sender: MessageSender | None = None
    ) -> None:
        """Remueve un jugador de todos los mapas y limpia ocupación."""
        session = self._players_by_id.get(user_id)
        if session is None or (
            expected_sender is not None and session.sender is not expected_sender
        ):
            return
        for map_id in session.maps.copy():
            self.remove_player(map_id, user_id, expected_sender)

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
        session = self._players_by_id.get(user_id)
        return session.sender if session is not None else None

    def find_player_by_username(self, username: str) -> int | None:
        """Busca jugador online por username (case-insensitive).

        Returns:
            int | None: user_id encontrado o None.
        """
        entries = self._players_by_name.get(self._normalized_name(username))
        return next(iter(entries)) if entries else None

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
        session = self._players_by_id.get(user_id)
        return session.username if session is not None else None

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

        return self.get_player_username(user_id)

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

        return self.get_player_message_sender(user_id)

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
        return list(
            dict.fromkeys(
                username
                for players in self._players_by_map.values()
                for _sender, username in players.values()
                if username
            )
        )

    def get_all_connected_user_ids(self) -> list[int]:
        """user_ids de todos los jugadores conectados (únicos).

        Returns:
            list[int]: user_ids conectados.
        """
        return list(
            dict.fromkeys(
                user_id for players in self._players_by_map.values() for user_id in players
            )
        )
