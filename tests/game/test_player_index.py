"""Tests unitarios para PlayerIndex (jugadores por mapa y ocupación)."""

from types import SimpleNamespace

from src.game.player_index import PlayerIndex


def make_sender(name: str) -> SimpleNamespace:
    """Crea un sender liviano para pruebas."""
    return SimpleNamespace(name=name)


def test_add_and_remove_player_updates_occupation() -> None:
    """Agregar y remover limpia ocupación y storage."""
    tile_occupation: dict[tuple[int, int, int], str] = {(1, 10, 10): "player:999"}
    index = PlayerIndex(tile_occupation)

    index.add_player(1, 1, make_sender("s1"), "Alice")
    assert index.players_by_map[1][1][1] == "Alice"

    index.remove_player(1, 1)
    assert 1 not in index.players_by_map
    assert (1, 10, 10) in tile_occupation  # no se tocó otro jugador


def test_remove_player_from_all_maps() -> None:
    """Remove all maps limpia ocupación y mapas vacíos."""
    tile_occupation: dict[tuple[int, int, int], str] = {
        (1, 1, 1): "player:1",
        (2, 2, 2): "player:1",
    }
    index = PlayerIndex(tile_occupation)
    index.add_player(1, 1, make_sender("s1"), "Alice")
    index.add_player(2, 1, make_sender("s1"), "Alice")

    index.remove_player_from_all_maps(1)

    assert not index.players_by_map
    assert (1, 1, 1) not in tile_occupation
    assert (2, 2, 2) not in tile_occupation


def test_queries_by_username_and_sender() -> None:
    """Consultas de username, sender y búsqueda por nombre."""
    tile_occupation: dict[tuple[int, int, int], str] = {}
    index = PlayerIndex(tile_occupation)
    sender = make_sender("s1")
    index.add_player(1, 42, sender, "Alice")

    assert index.find_player_by_username("alice") == 42
    assert index.get_player_message_sender(42) is sender
    assert index.get_username(42) == "Alice"
    assert index.get_message_sender(42) is sender


def test_lists_and_counts() -> None:
    """Listados de usuarios, mapas y conteos."""
    tile_occupation: dict[tuple[int, int, int], str] = {}
    index = PlayerIndex(tile_occupation)
    index.add_player(1, 1, make_sender("s1"), "A")
    index.add_player(2, 2, make_sender("s2"), "B")

    assert set(index.get_maps_with_players()) == {1, 2}
    assert set(index.get_players_in_map(1)) == {1}
    assert index.get_player_count_in_map(2) == 1
    assert set(index.get_all_connected_players()) == {"A", "B"}
    assert set(index.get_all_connected_user_ids()) == {1, 2}
    online = index.get_all_online_players()
    assert (1, "A", 1) in online
    assert (2, "B", 2) in online


def test_get_all_message_senders_in_map_with_exclude() -> None:
    """Obtiene senders excluyendo un usuario."""
    tile_occupation: dict[tuple[int, int, int], str] = {}
    index = PlayerIndex(tile_occupation)
    s1 = make_sender("s1")
    s2 = make_sender("s2")
    index.add_player(1, 1, s1, "A")
    index.add_player(1, 2, s2, "B")

    senders = index.get_all_message_senders_in_map(1, exclude_user_id=1)
    assert senders == [s2]
