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
