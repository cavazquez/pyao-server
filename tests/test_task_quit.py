"""Tests para TaskQuit."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.client_connection import ClientConnection
from src.map_manager import MapManager
from src.message_sender import MessageSender
from src.packet_id import ClientPacketID
from src.task_quit import TaskQuit


@pytest.mark.asyncio
async def test_task_quit_success() -> None:
    """Verifica que TaskQuit desconecte correctamente al jugador."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()
    writer.close = MagicMock()
    writer.wait_closed = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)

    # Mock del player_repo
    player_repo = MagicMock()
    player_repo.get_position = AsyncMock(return_value={"x": 50, "y": 50, "map": 1, "heading": 3})

    # Crear MapManager con jugadores
    map_manager = MapManager()
    sender1 = MagicMock()
    sender1.send_character_remove = AsyncMock()
    sender2 = MagicMock()
    sender2.send_character_remove = AsyncMock()
    
    # Agregar jugadores al mapa
    map_manager.add_player(1, 100, message_sender, "TestUser")
    map_manager.add_player(1, 101, sender1, "OtherUser1")
    map_manager.add_player(1, 102, sender2, "OtherUser2")

    # Datos de sesión
    session_data: dict[str, dict[str, int] | int | str] = {
        "user_id": 100,
        "username": "TestUser",
    }

    # Construir paquete QUIT (solo PacketID)
    data = bytes([ClientPacketID.QUIT])

    task = TaskQuit(data, message_sender, player_repo, map_manager, session_data)
    await task.execute()

    # Verificar que se obtuvo la posición
    player_repo.get_position.assert_called_once_with(100)

    # Verificar que se envió CHARACTER_REMOVE a otros jugadores
    sender1.send_character_remove.assert_called_once_with(100)
    sender2.send_character_remove.assert_called_once_with(100)

    # Verificar que el jugador fue removido del MapManager
    assert 100 not in map_manager.get_players_in_map(1)

    # Verificar que la sesión fue limpiada
    assert len(session_data) == 0

    # Verificar que la conexión fue cerrada
    writer.close.assert_called_once()
    writer.wait_closed.assert_called_once()


@pytest.mark.asyncio
async def test_task_quit_no_other_players() -> None:
    """Verifica que TaskQuit funcione cuando no hay otros jugadores en el mapa."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()
    writer.close = MagicMock()
    writer.wait_closed = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)

    # Mock del player_repo
    player_repo = MagicMock()
    player_repo.get_position = AsyncMock(return_value={"x": 50, "y": 50, "map": 1, "heading": 3})

    # Crear MapManager con solo el jugador que se desconecta
    map_manager = MapManager()
    map_manager.add_player(1, 100, message_sender, "TestUser")

    session_data: dict[str, dict[str, int] | int | str] = {
        "user_id": 100,
        "username": "TestUser",
    }

    data = bytes([ClientPacketID.QUIT])

    task = TaskQuit(data, message_sender, player_repo, map_manager, session_data)
    await task.execute()

    # Verificar que el jugador fue removido
    assert 100 not in map_manager.get_players_in_map(1)

    # Verificar que la conexión fue cerrada
    writer.close.assert_called_once()
    writer.wait_closed.assert_called_once()


@pytest.mark.asyncio
async def test_task_quit_no_session() -> None:
    """Verifica que TaskQuit maneje el caso sin sesión activa."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()
    writer.close = MagicMock()
    writer.wait_closed = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)

    # Sin session_data
    session_data: dict[str, dict[str, int]] = {}

    data = bytes([ClientPacketID.QUIT])

    task = TaskQuit(data, message_sender, None, None, session_data)
    await task.execute()

    # El test pasa si no hay excepciones (solo se loguea info)
    # La conexión no debe cerrarse si no hay sesión
    writer.close.assert_not_called()


@pytest.mark.asyncio
async def test_task_quit_no_position() -> None:
    """Verifica que TaskQuit funcione cuando el jugador no tiene posición."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()
    writer.close = MagicMock()
    writer.wait_closed = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)

    # Mock del player_repo que retorna None
    player_repo = MagicMock()
    player_repo.get_position = AsyncMock(return_value=None)

    map_manager = MapManager()
    map_manager.add_player(1, 100, message_sender, "TestUser")

    session_data: dict[str, dict[str, int] | int | str] = {
        "user_id": 100,
        "username": "TestUser",
    }

    data = bytes([ClientPacketID.QUIT])

    task = TaskQuit(data, message_sender, player_repo, map_manager, session_data)
    await task.execute()

    # Verificar que el jugador fue removido del MapManager
    assert 100 not in map_manager.get_players_in_map(1)

    # Verificar que la conexión fue cerrada
    writer.close.assert_called_once()
    writer.wait_closed.assert_called_once()


@pytest.mark.asyncio
async def test_task_quit_no_map_manager() -> None:
    """Verifica que TaskQuit funcione sin MapManager."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()
    writer.close = MagicMock()
    writer.wait_closed = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)

    session_data: dict[str, dict[str, int] | int | str] = {
        "user_id": 100,
        "username": "TestUser",
    }

    data = bytes([ClientPacketID.QUIT])

    task = TaskQuit(data, message_sender, None, None, session_data)
    await task.execute()

    # Verificar que la sesión fue limpiada
    assert len(session_data) == 0

    # Verificar que la conexión fue cerrada
    writer.close.assert_called_once()
    writer.wait_closed.assert_called_once()


@pytest.mark.asyncio
async def test_task_quit_clears_session() -> None:
    """Verifica que TaskQuit limpie correctamente la sesión."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()
    writer.close = MagicMock()
    writer.wait_closed = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)

    map_manager = MapManager()

    # Sesión con múltiples datos
    session_data: dict[str, dict[str, int] | int | str] = {
        "user_id": 100,
        "username": "TestUser",
        "char_index": 1,
    }

    data = bytes([ClientPacketID.QUIT])

    task = TaskQuit(data, message_sender, None, map_manager, session_data)
    await task.execute()

    # Verificar que todos los datos de sesión fueron limpiados
    assert len(session_data) == 0
    assert "user_id" not in session_data
    assert "username" not in session_data
    assert "char_index" not in session_data


@pytest.mark.asyncio
async def test_task_quit_notifies_multiple_maps() -> None:
    """Verifica que TaskQuit remueva al jugador de todos los mapas."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()
    writer.close = MagicMock()
    writer.wait_closed = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)

    player_repo = MagicMock()
    player_repo.get_position = AsyncMock(return_value={"x": 50, "y": 50, "map": 1, "heading": 3})

    # Crear MapManager - agregar jugador en múltiples mapas (caso hipotético)
    map_manager = MapManager()
    map_manager.add_player(1, 100, message_sender, "TestUser")
    # Simular que el jugador está en otro mapa también
    map_manager.add_player(2, 100, message_sender, "TestUser")

    session_data: dict[str, dict[str, int] | int | str] = {
        "user_id": 100,
        "username": "TestUser",
    }

    data = bytes([ClientPacketID.QUIT])

    task = TaskQuit(data, message_sender, player_repo, map_manager, session_data)
    await task.execute()

    # Verificar que el jugador fue removido de todos los mapas
    assert 100 not in map_manager.get_players_in_map(1)
    assert 100 not in map_manager.get_players_in_map(2)

    # Verificar que la conexión fue cerrada
    writer.close.assert_called_once()
    writer.wait_closed.assert_called_once()
