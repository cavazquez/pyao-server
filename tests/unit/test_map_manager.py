"""Tests para MapManager."""

import asyncio
import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.game.map_manager import MapManager
from src.messaging.message_sender import MessageSender
from src.models.npc import NPC
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
    assert not username


# Tests para NPCs
@pytest.fixture
def mock_npc() -> NPC:
    """Fixture que crea un NPC mock."""
    return NPC(
        npc_id=1,
        char_index=10001,
        instance_id="npc-1",
        map_id=1,
        x=10,
        y=10,
        heading=3,
        name="Test NPC",
        description="Test",
        body_id=1,
        head_id=0,
        hp=100,
        max_hp=100,
        level=1,
        is_hostile=False,
        is_attackable=True,
    )


def test_move_npc(map_manager: MapManager, mock_npc: NPC) -> None:
    """Test move_npc actualiza tile occupation."""
    map_manager.add_npc(1, mock_npc)

    # Mover NPC
    map_manager.move_npc(1, 10001, 10, 10, 15, 15)

    # Verificar que el tile anterior está libre
    assert (1, 10, 10) not in map_manager._tile_occupation

    # Verificar que el nuevo tile está ocupado
    assert map_manager._tile_occupation[1, 15, 15] == "npc:npc-1"


def test_remove_npc_clears_tile_occupation(map_manager: MapManager, mock_npc: NPC) -> None:
    """Test remove_npc limpia tile occupation."""
    map_manager.add_npc(1, mock_npc)

    # Verificar que el tile está ocupado
    assert (1, 10, 10) in map_manager._tile_occupation

    # Remover NPC
    map_manager.remove_npc(1, "npc-1")

    # Verificar que el tile está libre
    assert (1, 10, 10) not in map_manager._tile_occupation
    assert 1 not in map_manager._npcs_by_map


def test_remove_npc_nonexistent(map_manager: MapManager) -> None:
    """Test remove_npc con NPC inexistente no falla."""
    map_manager.remove_npc(1, "nonexistent")
    # No debe lanzar excepción


# Tests para Ground Items
def test_add_ground_item(map_manager: MapManager) -> None:
    """Test add_ground_item agrega item correctamente."""
    item = {"item_id": 1, "quantity": 5, "grh_index": 100}
    map_manager.add_ground_item(1, 10, 20, item)

    items = map_manager.get_ground_items(1, 10, 20)
    assert len(items) == 1
    assert items[0] == item


def test_add_ground_item_max_limit(map_manager: MapManager) -> None:
    """Test add_ground_item respeta límite de items por tile."""
    item = {"item_id": 1, "quantity": 1, "grh_index": 100}

    # Agregar 10 items (límite)
    for _i in range(10):
        map_manager.add_ground_item(1, 10, 20, item)

    items = map_manager.get_ground_items(1, 10, 20)
    assert len(items) == 10

    # Intentar agregar uno más (no debe agregarse)
    map_manager.add_ground_item(1, 10, 20, item)
    items = map_manager.get_ground_items(1, 10, 20)
    assert len(items) == 10  # Sigue siendo 10


def test_remove_ground_item(map_manager: MapManager) -> None:
    """Test remove_ground_item remueve item correctamente."""
    item1 = {"item_id": 1, "quantity": 1, "grh_index": 100}
    item2 = {"item_id": 2, "quantity": 2, "grh_index": 200}

    map_manager.add_ground_item(1, 10, 20, item1)
    map_manager.add_ground_item(1, 10, 20, item2)

    # Remover primer item
    removed = map_manager.remove_ground_item(1, 10, 20, item_index=0)
    assert removed == item1

    items = map_manager.get_ground_items(1, 10, 20)
    assert len(items) == 1
    assert items[0] == item2


def test_remove_ground_item_nonexistent(map_manager: MapManager) -> None:
    """Test remove_ground_item con posición sin items."""
    removed = map_manager.remove_ground_item(1, 10, 20)
    assert removed is None


def test_remove_ground_item_invalid_index(map_manager: MapManager) -> None:
    """Test remove_ground_item con índice inválido."""
    item = {"item_id": 1, "quantity": 1, "grh_index": 100}
    map_manager.add_ground_item(1, 10, 20, item)

    # Intentar remover índice 10 cuando solo hay 1 item
    removed = map_manager.remove_ground_item(1, 10, 20, item_index=10)
    assert removed is None


def test_clear_ground_items(map_manager: MapManager) -> None:
    """Test clear_ground_items limpia todos los items de un mapa."""
    item = {"item_id": 1, "quantity": 1, "grh_index": 100}

    # Agregar items en diferentes posiciones
    map_manager.add_ground_item(1, 10, 20, item)
    map_manager.add_ground_item(1, 15, 25, item)
    map_manager.add_ground_item(1, 20, 30, item)

    # Agregar items en otro mapa (no deben ser removidos)
    map_manager.add_ground_item(2, 10, 20, item)

    # Limpiar mapa 1
    count = map_manager.clear_ground_items(1)

    assert count == 3
    assert map_manager.get_ground_items(1, 10, 20) == []
    assert map_manager.get_ground_items(1, 15, 25) == []
    assert map_manager.get_ground_items(1, 20, 30) == []

    # Verificar que mapa 2 no fue afectado
    assert len(map_manager.get_ground_items(2, 10, 20)) == 1


def test_clear_ground_items_empty_map(map_manager: MapManager) -> None:
    """Test clear_ground_items en mapa sin items."""
    count = map_manager.clear_ground_items(1)
    assert count == 0


def test_get_ground_items_count(map_manager: MapManager) -> None:
    """Test get_ground_items_count cuenta items correctamente."""
    item = {"item_id": 1, "quantity": 1, "grh_index": 100}

    # Agregar items en diferentes posiciones del mapa 1
    map_manager.add_ground_item(1, 10, 20, item)
    map_manager.add_ground_item(1, 15, 25, item)
    map_manager.add_ground_item(1, 20, 30, item)

    # Agregar items en mapa 2 (no deben contarse)
    map_manager.add_ground_item(2, 10, 20, item)

    count = map_manager.get_ground_items_count(1)
    assert count == 3

    count = map_manager.get_ground_items_count(2)
    assert count == 1


def test_get_ground_items_count_empty_map(map_manager: MapManager) -> None:
    """Test get_ground_items_count en mapa sin items."""
    count = map_manager.get_ground_items_count(1)
    assert count == 0


# Tests para Tile Blocking
def test_block_tile(map_manager: MapManager) -> None:
    """Test block_tile bloquea un tile (puerta cerrada)."""
    map_manager.block_tile(1, 10, 20)
    assert (10, 20) in map_manager._closed_doors[1]


def test_unblock_tile(map_manager: MapManager) -> None:
    """Test unblock_tile desbloquea un tile (puerta abierta)."""
    map_manager.block_tile(1, 10, 20)
    assert (10, 20) in map_manager._closed_doors[1]

    map_manager.unblock_tile(1, 10, 20)
    assert (10, 20) not in map_manager._closed_doors[1]


def test_unblock_tile_nonexistent(map_manager: MapManager) -> None:
    """Test unblock_tile con tile no bloqueado no falla."""
    map_manager.unblock_tile(1, 10, 20)
    # No debe lanzar excepción


def test_is_door_closed(map_manager: MapManager) -> None:
    """Test is_door_closed verifica puertas cerradas."""
    # Agregar puerta cerrada
    map_manager._closed_doors[1] = {(10, 20)}

    assert map_manager.is_door_closed(1, 10, 20) is True
    assert map_manager.is_door_closed(1, 15, 25) is False


def test_is_door_closed_nonexistent_map(map_manager: MapManager) -> None:
    """Test is_door_closed en mapa sin puertas."""
    assert map_manager.is_door_closed(1, 10, 20) is False


# Tests para Persistencia
@pytest.mark.asyncio
async def test_persist_ground_items(map_manager: MapManager) -> None:
    """Test _persist_ground_items persiste items en Redis."""
    mock_repo = MagicMock()
    mock_repo.save_ground_items = AsyncMock()
    map_manager.ground_items_repo = mock_repo

    item = {"item_id": 1, "quantity": 1, "grh_index": 100}
    map_manager.add_ground_item(1, 10, 20, item)
    map_manager.add_ground_item(1, 15, 25, item)

    await map_manager._persist_ground_items(1)

    mock_repo.save_ground_items.assert_called_once()
    call_args = mock_repo.save_ground_items.call_args[0]
    assert call_args[0] == 1  # map_id
    map_items = call_args[1]
    assert (10, 20) in map_items
    assert (15, 25) in map_items


@pytest.mark.asyncio
async def test_persist_ground_items_no_repo(map_manager: MapManager) -> None:
    """Test _persist_ground_items sin repositorio no falla."""
    map_manager.ground_items_repo = None

    item = {"item_id": 1, "quantity": 1, "grh_index": 100}
    map_manager.add_ground_item(1, 10, 20, item)

    await map_manager._persist_ground_items(1)
    # No debe lanzar excepción


@pytest.mark.asyncio
async def test_load_ground_items(map_manager: MapManager) -> None:
    """Test load_ground_items carga items desde Redis."""
    mock_repo = MagicMock()
    mock_repo.load_ground_items = AsyncMock(
        return_value={
            (10, 20): [{"item_id": 1, "quantity": 1, "grh_index": 100}],
            (15, 25): [{"item_id": 2, "quantity": 2, "grh_index": 200}],
        }
    )
    map_manager.ground_items_repo = mock_repo

    await map_manager.load_ground_items(1)

    items1 = map_manager.get_ground_items(1, 10, 20)
    items2 = map_manager.get_ground_items(1, 15, 25)

    assert len(items1) == 1
    assert items1[0]["item_id"] == 1
    assert len(items2) == 1
    assert items2[0]["item_id"] == 2


@pytest.mark.asyncio
async def test_load_ground_items_no_repo(map_manager: MapManager) -> None:
    """Test load_ground_items sin repositorio no falla."""
    map_manager.ground_items_repo = None

    await map_manager.load_ground_items(1)
    # No debe lanzar excepción


def test_get_npc_by_char_index_nonexistent(map_manager: MapManager) -> None:
    """Test get_npc_by_char_index retorna None cuando no existe."""
    npc = map_manager.get_npc_by_char_index(1, 10001)
    assert npc is None


def test_get_npc_by_char_index(map_manager: MapManager, mock_npc: NPC) -> None:
    """Test get_npc_by_char_index encuentra NPC por char_index."""
    map_manager.add_npc(1, mock_npc)

    npc = map_manager.get_npc_by_char_index(1, 10001)
    assert npc is not None
    assert npc.instance_id == "npc-1"


def test_remove_player_from_all_maps_clears_tile_occupation(
    map_manager: MapManager, message_sender: MessageSender
) -> None:
    """Test remove_player_from_all_maps limpia tile occupation."""
    # Agregar jugador y marcar tile como ocupado
    map_manager.add_player(1, 100, message_sender, username="TestUser")
    map_manager._tile_occupation[1, 10, 20] = "player:100"

    # Remover jugador de todos los mapas
    map_manager.remove_player_from_all_maps(100)

    # Verificar que el tile está libre
    assert (1, 10, 20) not in map_manager._tile_occupation
    assert 1 not in map_manager._players_by_map


def test_remove_player_from_all_maps_multiple_maps(
    map_manager: MapManager, message_sender: MessageSender
) -> None:
    """Test remove_player_from_all_maps limpia de múltiples mapas."""
    # Agregar jugador en múltiples mapas
    map_manager.add_player(1, 100, message_sender, username="TestUser")
    map_manager.add_player(2, 100, message_sender, username="TestUser")

    # Marcar tiles como ocupados
    map_manager._tile_occupation[1, 10, 20] = "player:100"
    map_manager._tile_occupation[2, 15, 25] = "player:100"

    # Remover jugador de todos los mapas
    map_manager.remove_player_from_all_maps(100)

    # Verificar que ambos tiles están libres
    assert (1, 10, 20) not in map_manager._tile_occupation
    assert (2, 15, 25) not in map_manager._tile_occupation
    assert 1 not in map_manager._players_by_map
    assert 2 not in map_manager._players_by_map


def test_remove_ground_item_clears_when_empty(map_manager: MapManager) -> None:
    """Test remove_ground_item limpia la posición cuando es el último item."""
    item = {"item_id": 1, "quantity": 1, "grh_index": 100}
    map_manager.add_ground_item(1, 10, 20, item)

    # Remover el único item
    removed = map_manager.remove_ground_item(1, 10, 20)

    assert removed == item
    # Verificar que la posición ya no existe en _ground_items
    assert (1, 10, 20) not in map_manager._ground_items


@pytest.mark.asyncio
async def test_remove_ground_item_persists_when_repo_exists(map_manager: MapManager) -> None:
    """Test remove_ground_item persiste cuando hay repositorio."""
    mock_repo = MagicMock()
    mock_repo.save_ground_items = AsyncMock()
    map_manager.ground_items_repo = mock_repo

    item = {"item_id": 1, "quantity": 1, "grh_index": 100}
    map_manager.add_ground_item(1, 10, 20, item)

    # Remover item (debe persistir)
    removed = map_manager.remove_ground_item(1, 10, 20)

    assert removed == item
    # Dar tiempo para que la tarea asíncrona se ejecute
    await asyncio.sleep(0.1)
    # Verificar que se intentó persistir
    assert mock_repo.save_ground_items.called


# Tests para carga de datos de mapas
def test_load_metadata_file_nonexistent() -> None:
    """Test _load_metadata_file con archivo inexistente."""
    nonexistent_path = Path("/nonexistent/metadata.json")
    width, height, blocked = MapManager._load_metadata_file(nonexistent_path)

    assert width == 100  # Valores por defecto
    assert height == 100
    assert blocked is None


def test_load_metadata_file_simple_json() -> None:
    """Test _load_metadata_file con JSON simple."""
    with tempfile.NamedTemporaryFile(encoding="utf-8", mode="w", suffix=".json", delete=False) as f:
        metadata = {"w": 150, "h": 200, "blocked_tiles": [{"x": 10, "y": 20}]}
        json.dump(metadata, f)
        temp_path = Path(f.name)

    try:
        width, height, blocked = MapManager._load_metadata_file(temp_path)

        assert width == 150
        assert height == 200
        assert blocked is not None
        assert len(blocked) == 1
    finally:
        temp_path.unlink()


def test_load_metadata_file_list_json() -> None:
    """Test _load_metadata_file con JSON como lista."""
    with tempfile.NamedTemporaryFile(encoding="utf-8", mode="w", suffix=".json", delete=False) as f:
        metadata = [{"w": 120, "h": 180}]
        json.dump(metadata, f)
        temp_path = Path(f.name)

    try:
        width, height, _blocked = MapManager._load_metadata_file(temp_path)

        assert width == 120
        assert height == 180
    finally:
        temp_path.unlink()


def test_load_blocked_file_nonexistent() -> None:
    """Test _load_blocked_file con archivo inexistente."""
    nonexistent_path = Path("/nonexistent/blocked.json")
    blocked = MapManager._load_blocked_file(nonexistent_path)

    assert blocked is None


def test_load_blocked_file_simple_json() -> None:
    """Test _load_blocked_file con JSON simple."""
    with tempfile.NamedTemporaryFile(encoding="utf-8", mode="w", suffix=".json", delete=False) as f:
        blocked_data = [{"x": 10, "y": 20}, {"x": 15, "y": 25}]
        json.dump(blocked_data, f)
        temp_path = Path(f.name)

    try:
        blocked = MapManager._load_blocked_file(temp_path)

        assert blocked is not None
        assert len(blocked) == 2
    finally:
        temp_path.unlink()


def test_load_map_data_basic(map_manager: MapManager) -> None:
    """Test load_map_data carga datos básicos de un mapa."""
    with tempfile.TemporaryDirectory() as tmpdir:
        metadata_path = Path(tmpdir) / "metadata_001-064.json"
        metadata = {"w": 100, "h": 100}
        with metadata_path.open("w") as f:
            json.dump(metadata, f)

        # Crear archivo blocked vacío
        blocked_path = Path(tmpdir) / "blocked_001-050.json"
        blocked_path.write_text("[]")

        map_manager.load_map_data(1, metadata_path)

        # Verificar que se cargó el tamaño del mapa
        assert map_manager.get_map_size(1) == (100, 100)
        # Verificar que se inicializaron los tiles bloqueados (aunque esté vacío)
        assert 1 in map_manager._blocked_tiles


def test_get_map_size_default(map_manager: MapManager) -> None:
    """Test get_map_size retorna valores por defecto si no está cargado."""
    size = map_manager.get_map_size(999)
    assert size == (100, 100)  # Valores por defecto


def test_get_exit_tile(map_manager: MapManager) -> None:
    """Test get_exit_tile retorna exit tile si existe."""
    # Agregar exit tile manualmente
    map_manager._exit_tiles[1, 10, 20] = {"to_map": 2, "to_x": 15, "to_y": 25}

    exit_tile = map_manager.get_exit_tile(1, 10, 20)
    assert exit_tile is not None
    assert exit_tile["to_map"] == 2
    assert exit_tile["to_x"] == 15
    assert exit_tile["to_y"] == 25


def test_get_exit_tile_nonexistent(map_manager: MapManager) -> None:
    """Test get_exit_tile retorna None si no existe."""
    exit_tile = map_manager.get_exit_tile(1, 10, 20)
    assert exit_tile is None
