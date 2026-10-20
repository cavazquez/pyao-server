"""Enumerar sesiones conserva orden y elimina duplicados durante una transición."""

from unittest.mock import MagicMock

from src.game.player_index import PlayerIndex
from src.game.tile_occupation import TileOccupation


def test_duplicate_map_membership_does_not_duplicate_connected_players():
    """Un jugador temporalmente en dos mapas se lista sólo en su primera aparición."""
    index = PlayerIndex(TileOccupation())
    sender = MagicMock()
    index.add_player(2, 7, sender, "Peña")
    index.add_player(2, 4, sender, "Beto")
    index.add_player(3, 7, sender, "Peña")
    index.add_player(3, 11, sender, "")
    index.add_player(3, 8, sender, "beto")
    assert index.get_all_connected_user_ids() == [7, 4, 11, 8]
    assert index.get_all_connected_players() == ["Peña", "Beto", "beto"]
    index.remove_player(2, 7)
    assert index.get_all_connected_user_ids() == [4, 7, 11, 8]
    assert index.get_all_connected_players() == ["Beto", "Peña", "beto"]
