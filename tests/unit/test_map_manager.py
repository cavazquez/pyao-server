"""Tests para MapManager."""

from unittest.mock import MagicMock

import pytest

from src.game.map_manager import MapManager
from src.messaging.message_sender import MessageSender
from src.network.client_connection import ClientConnection


@pytest.fixture
def map_manager() -> MapManager:
    """Fixture que crea un MapManager.

    Returns:
        MapManager instanciado.
    """
    return MapManager()


@pytest.fixture
def message_sender() -> MessageSender:
    """Fixture que crea un MessageSender mock.

    Returns:
        MessageSender con conexión mock.
    """
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    return MessageSender(connection)


def test_map_manager_init(map_manager: MapManager) -> None:
    """Verifica que MapManager se inicialice correctamente."""
    assert map_manager is not None
    assert map_manager.get_player_count_in_map(1) == 0


def test_add_player(map_manager: MapManager, message_sender: MessageSender) -> None:
    """Verifica que se pueda agregar un jugador a un mapa."""
    map_manager.add_player(1, 100, message_sender)

    assert map_manager.get_player_count_in_map(1) == 1
    assert 100 in map_manager.get_players_in_map(1)


def test_add_multiple_players_same_map(
    map_manager: MapManager, message_sender: MessageSender
) -> None:
    """Verifica que se puedan agregar múltiples jugadores al mismo mapa."""
    map_manager.add_player(1, 100, message_sender)
    map_manager.add_player(1, 101, message_sender)
    map_manager.add_player(1, 102, message_sender)

    assert map_manager.get_player_count_in_map(1) == 3
    players = map_manager.get_players_in_map(1)
    assert 100 in players
    assert 101 in players
    assert 102 in players


def test_add_players_different_maps(map_manager: MapManager, message_sender: MessageSender) -> None:
    """Verifica que se puedan agregar jugadores a diferentes mapas."""
    map_manager.add_player(1, 100, message_sender)
    map_manager.add_player(2, 101, message_sender)
    map_manager.add_player(3, 102, message_sender)

    assert map_manager.get_player_count_in_map(1) == 1
    assert map_manager.get_player_count_in_map(2) == 1
    assert map_manager.get_player_count_in_map(3) == 1


def test_remove_player(map_manager: MapManager, message_sender: MessageSender) -> None:
    """Verifica que se pueda remover un jugador de un mapa."""
    map_manager.add_player(1, 100, message_sender)
    assert map_manager.get_player_count_in_map(1) == 1

    map_manager.remove_player(1, 100)
    assert map_manager.get_player_count_in_map(1) == 0


def test_remove_player_cleans_empty_map(
    map_manager: MapManager, message_sender: MessageSender
) -> None:
    """Verifica que se limpie un mapa vacío después de remover el último jugador."""
    map_manager.add_player(1, 100, message_sender)
    map_manager.remove_player(1, 100)

    # El mapa debería estar limpio (no debería existir en la estructura interna)
    assert map_manager.get_player_count_in_map(1) == 0
    assert map_manager.get_players_in_map(1) == []


def test_remove_nonexistent_player(map_manager: MapManager) -> None:
    """Verifica que remover un jugador inexistente no cause errores."""
    # No debería lanzar excepción
    map_manager.remove_player(1, 999)
    assert map_manager.get_player_count_in_map(1) == 0


def test_get_players_in_map(map_manager: MapManager, message_sender: MessageSender) -> None:
    """Verifica que se obtengan correctamente los jugadores en un mapa."""
    map_manager.add_player(1, 100, message_sender)
    map_manager.add_player(1, 101, message_sender)
    map_manager.add_player(2, 102, message_sender)

    players_map1 = map_manager.get_players_in_map(1)
    assert len(players_map1) == 2
    assert 100 in players_map1
    assert 101 in players_map1
    assert 102 not in players_map1


def test_get_players_in_map_exclude_user(
    map_manager: MapManager, message_sender: MessageSender
) -> None:
    """Verifica que se pueda excluir un jugador al obtener la lista."""
    map_manager.add_player(1, 100, message_sender)
    map_manager.add_player(1, 101, message_sender)
    map_manager.add_player(1, 102, message_sender)

    players = map_manager.get_players_in_map(1, exclude_user_id=101)
    assert len(players) == 2
    assert 100 in players
    assert 101 not in players
    assert 102 in players


def test_get_players_in_empty_map(map_manager: MapManager) -> None:
    """Verifica que obtener jugadores de un mapa vacío retorne lista vacía."""
    players = map_manager.get_players_in_map(999)
    assert players == []


def test_get_message_sender(map_manager: MapManager, message_sender: MessageSender) -> None:
    """Verifica que se pueda obtener el MessageSender de un jugador."""
    map_manager.add_player(1, 100, message_sender)

    sender = map_manager.get_message_sender(100)
    assert sender is message_sender


def test_get_message_sender_nonexistent(map_manager: MapManager) -> None:
    """Verifica que obtener MessageSender de jugador inexistente retorne None."""
    sender = map_manager.get_message_sender(999)
    assert sender is None


def test_get_all_message_senders_in_map(
    map_manager: MapManager, message_sender: MessageSender
) -> None:
    """Verifica que se obtengan todos los MessageSenders de un mapa."""
    map_manager.add_player(1, 100, message_sender)
    map_manager.add_player(1, 101, message_sender)
    map_manager.add_player(1, 102, message_sender)

    senders = map_manager.get_all_message_senders_in_map(1)
    assert len(senders) == 3


def test_get_all_message_senders_exclude_user(
    map_manager: MapManager, message_sender: MessageSender
) -> None:
    """Verifica que se pueda excluir un jugador al obtener MessageSenders."""
    map_manager.add_player(1, 100, message_sender)
    map_manager.add_player(1, 101, message_sender)
    map_manager.add_player(1, 102, message_sender)

    senders = map_manager.get_all_message_senders_in_map(1, exclude_user_id=101)
    assert len(senders) == 2


def test_get_all_message_senders_empty_map(map_manager: MapManager) -> None:
    """Verifica que obtener MessageSenders de mapa vacío retorne lista vacía."""
    senders = map_manager.get_all_message_senders_in_map(999)
    assert senders == []


def test_get_player_count_in_map(map_manager: MapManager, message_sender: MessageSender) -> None:
    """Verifica que se obtenga correctamente el conteo de jugadores."""
    assert map_manager.get_player_count_in_map(1) == 0

    map_manager.add_player(1, 100, message_sender)
    assert map_manager.get_player_count_in_map(1) == 1

    map_manager.add_player(1, 101, message_sender)
    assert map_manager.get_player_count_in_map(1) == 2

    map_manager.remove_player(1, 100)
    assert map_manager.get_player_count_in_map(1) == 1


def test_remove_player_from_all_maps(
    map_manager: MapManager, message_sender: MessageSender
) -> None:
    """Verifica que se pueda remover un jugador de todos los mapas."""
    map_manager.add_player(1, 100, message_sender)
    map_manager.add_player(2, 100, message_sender)
    map_manager.add_player(3, 100, message_sender)

    assert map_manager.get_player_count_in_map(1) == 1
    assert map_manager.get_player_count_in_map(2) == 1
    assert map_manager.get_player_count_in_map(3) == 1

    map_manager.remove_player_from_all_maps(100)

    assert map_manager.get_player_count_in_map(1) == 0
    assert map_manager.get_player_count_in_map(2) == 0
    assert map_manager.get_player_count_in_map(3) == 0


def test_remove_player_from_all_maps_cleans_empty_maps(
    map_manager: MapManager, message_sender: MessageSender
) -> None:
    """Verifica que se limpien mapas vacíos al remover de todos los mapas."""
    map_manager.add_player(1, 100, message_sender)
    map_manager.add_player(2, 100, message_sender)

    map_manager.remove_player_from_all_maps(100)

    # Los mapas deberían estar limpios
    assert map_manager.get_players_in_map(1) == []
    assert map_manager.get_players_in_map(2) == []


def test_multiple_operations(map_manager: MapManager, message_sender: MessageSender) -> None:
    """Verifica múltiples operaciones en secuencia."""
    # Agregar jugadores
    map_manager.add_player(1, 100, message_sender)
    map_manager.add_player(1, 101, message_sender)
    map_manager.add_player(2, 102, message_sender)

    assert map_manager.get_player_count_in_map(1) == 2
    assert map_manager.get_player_count_in_map(2) == 1

    # Remover un jugador
    map_manager.remove_player(1, 100)
    assert map_manager.get_player_count_in_map(1) == 1

    # Agregar más jugadores
    map_manager.add_player(1, 103, message_sender)
    assert map_manager.get_player_count_in_map(1) == 2

    # Obtener jugadores excluyendo uno
    players = map_manager.get_players_in_map(1, exclude_user_id=101)
    assert len(players) == 1
    assert 103 in players

    # Remover de todos los mapas
    map_manager.remove_player_from_all_maps(102)
    assert map_manager.get_player_count_in_map(2) == 0


def test_get_maps_with_players(map_manager: MapManager, message_sender: MessageSender) -> None:
    """Verifica que se obtengan correctamente los mapas con jugadores."""
    assert map_manager.get_maps_with_players() == []

    map_manager.add_player(1, 100, message_sender)
    map_manager.add_player(2, 101, message_sender)

    maps = map_manager.get_maps_with_players()
    assert 1 in maps
    assert 2 in maps
    assert len(maps) == 2

    map_manager.remove_player(1, 100)
    maps = map_manager.get_maps_with_players()
    assert 1 not in maps
    assert 2 in maps


def test_get_player_message_sender(map_manager: MapManager, message_sender: MessageSender) -> None:
    """Verifica get_player_message_sender."""
    map_manager.add_player(1, 100, message_sender)

    sender = map_manager.get_player_message_sender(100)
    assert sender is message_sender

    sender = map_manager.get_player_message_sender(999)
    assert sender is None


def test_find_player_by_username(map_manager: MapManager, message_sender: MessageSender) -> None:
    """Verifica find_player_by_username."""
    map_manager.add_player(1, 100, message_sender, username="TestUser")
    map_manager.add_player(2, 101, message_sender, username="AnotherUser")

    user_id = map_manager.find_player_by_username("testuser")  # Case-insensitive
    assert user_id == 100

    user_id = map_manager.find_player_by_username("ANOTHERUSER")
    assert user_id == 101

    user_id = map_manager.find_player_by_username("nonexistent")
    assert user_id is None

    user_id = map_manager.find_player_by_username("  testuser  ")  # Con espacios
    assert user_id == 100


def test_get_all_online_players(map_manager: MapManager, message_sender: MessageSender) -> None:
    """Verifica get_all_online_players."""
    map_manager.add_player(1, 100, message_sender, username="User1")
    map_manager.add_player(1, 101, message_sender, username="User2")
    map_manager.add_player(2, 102, message_sender, username="User3")

    players = map_manager.get_all_online_players()
    assert len(players) == 3
    assert (100, "User1", 1) in players
    assert (101, "User2", 1) in players
    assert (102, "User3", 2) in players


def test_get_player_username(map_manager: MapManager, message_sender: MessageSender) -> None:
    """Verifica get_player_username."""
    map_manager.add_player(1, 100, message_sender, username="TestUser")

    username = map_manager.get_player_username(100)
    assert username == "TestUser"

    username = map_manager.get_player_username(999)
    assert username is None


def test_get_username_with_map_id(map_manager: MapManager, message_sender: MessageSender) -> None:
    """Verifica get_username con map_id especificado."""
    map_manager.add_player(1, 100, message_sender, username="User1")
    map_manager.add_player(
        2, 100, message_sender, username="User2"
    )  # Mismo user_id, diferente mapa

    username = map_manager.get_username(100, map_id=1)
    assert username == "User1"

    username = map_manager.get_username(100, map_id=2)
    assert username == "User2"

    username = map_manager.get_username(100, map_id=999)
    assert username is None


def test_get_username_without_map_id(
    map_manager: MapManager, message_sender: MessageSender
) -> None:
    """Verifica get_username sin map_id (busca en todos los mapas)."""
    map_manager.add_player(1, 100, message_sender, username="User1")

    username = map_manager.get_username(100)
    assert username == "User1"

    username = map_manager.get_username(999)
    assert username is None


def test_get_message_sender_with_map_id(
    map_manager: MapManager, message_sender: MessageSender
) -> None:
    """Verifica get_message_sender con map_id especificado."""
    sender1 = MessageSender(message_sender.connection)
    sender2 = MessageSender(message_sender.connection)

    map_manager.add_player(1, 100, sender1, username="User1")
    map_manager.add_player(2, 100, sender2, username="User2")  # Mismo user_id, diferente mapa

    sender = map_manager.get_message_sender(100, map_id=1)
    assert sender is sender1

    sender = map_manager.get_message_sender(100, map_id=2)
    assert sender is sender2

    sender = map_manager.get_message_sender(100, map_id=999)
    assert sender is None


def test_get_message_sender_without_map_id(
    map_manager: MapManager, message_sender: MessageSender
) -> None:
    """Verifica get_message_sender sin map_id (busca en todos los mapas)."""
    map_manager.add_player(1, 100, message_sender)

    sender = map_manager.get_message_sender(100)
    assert sender is message_sender

    sender = map_manager.get_message_sender(999)
    assert sender is None


def test_get_all_connected_players(map_manager: MapManager, message_sender: MessageSender) -> None:
    """Verifica get_all_connected_players."""
    map_manager.add_player(1, 100, message_sender, username="User1")
    map_manager.add_player(1, 101, message_sender, username="User2")
    map_manager.add_player(2, 102, message_sender, username="User3")

    players = map_manager.get_all_connected_players()
    assert len(players) == 3
    assert "User1" in players
    assert "User2" in players
    assert "User3" in players


def test_get_all_connected_user_ids(map_manager: MapManager, message_sender: MessageSender) -> None:
    """Verifica get_all_connected_user_ids."""
    map_manager.add_player(1, 100, message_sender)
    map_manager.add_player(1, 101, message_sender)
    map_manager.add_player(2, 102, message_sender)

    user_ids = map_manager.get_all_connected_user_ids()
    assert len(user_ids) == 3
    assert 100 in user_ids
    assert 101 in user_ids
    assert 102 in user_ids


def test_add_player_with_username(map_manager: MapManager, message_sender: MessageSender) -> None:
    """Verifica que se pueda agregar un jugador con username."""
    map_manager.add_player(1, 100, message_sender, username="TestUser")

    username = map_manager.get_player_username(100)
    assert username == "TestUser"


def test_add_player_username_empty_string(
    map_manager: MapManager, message_sender: MessageSender
) -> None:
    """Verifica que se pueda agregar un jugador con username vacío."""
    map_manager.add_player(1, 100, message_sender, username="")

    username = map_manager.get_player_username(100)
    assert username == ""
