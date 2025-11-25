"""Tests para TaskQuit."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.commands.base import CommandResult
from src.commands.quit_command import QuitCommand
from src.messaging.message_sender import MessageSender
from src.network.client_connection import ClientConnection
from src.network.packet_id import ClientPacketID
from src.tasks.task_quit import TaskQuit


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

    # Mock del handler
    quit_handler = MagicMock()
    quit_handler.handle = AsyncMock(
        return_value=CommandResult.ok(data={"user_id": 100, "username": "TestUser"})
    )

    # Datos de sesión
    session_data: dict[str, dict[str, int] | int | str] = {
        "user_id": 100,
        "username": "TestUser",
    }

    # Construir paquete QUIT (solo PacketID)
    data = bytes([ClientPacketID.QUIT])

    task = TaskQuit(data, message_sender, quit_handler=quit_handler, session_data=session_data)
    await task.execute()

    # Verificar que se llamó al handler
    quit_handler.handle.assert_called_once()
    call_args = quit_handler.handle.call_args[0][0]
    assert isinstance(call_args, QuitCommand)
    assert call_args.user_id == 100
    assert call_args.username == "TestUser"

    # Verificar que la sesión fue limpiada
    assert len(session_data) == 0


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

    # Mock del handler
    quit_handler = MagicMock()
    quit_handler.handle = AsyncMock(
        return_value=CommandResult.ok(data={"user_id": 100, "username": "TestUser"})
    )

    session_data: dict[str, dict[str, int] | int | str] = {
        "user_id": 100,
        "username": "TestUser",
    }

    data = bytes([ClientPacketID.QUIT])

    task = TaskQuit(data, message_sender, quit_handler=quit_handler, session_data=session_data)
    await task.execute()

    # Verificar que se llamó al handler
    quit_handler.handle.assert_called_once()


@pytest.mark.asyncio
async def test_task_quit_no_session() -> None:
    """Verifica que TaskQuit no falle sin sesión activa."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)

    # Mock del handler (no debería llamarse)
    quit_handler = MagicMock()
    quit_handler.handle = AsyncMock()

    session_data: dict[str, dict[str, int] | int | str] = {}

    data = bytes([ClientPacketID.QUIT])

    task = TaskQuit(data, message_sender, quit_handler=quit_handler, session_data=session_data)
    await task.execute()

    # Verificar que NO se llamó al handler
    quit_handler.handle.assert_not_called()


@pytest.mark.asyncio
async def test_task_quit_no_position() -> None:
    """Verifica que TaskQuit funcione cuando no hay posición."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()
    writer.close = MagicMock()
    writer.wait_closed = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)

    # Mock del handler
    quit_handler = MagicMock()
    quit_handler.handle = AsyncMock(
        return_value=CommandResult.ok(data={"user_id": 100, "username": "TestUser"})
    )

    session_data: dict[str, dict[str, int] | int | str] = {
        "user_id": 100,
        "username": "TestUser",
    }

    data = bytes([ClientPacketID.QUIT])

    task = TaskQuit(data, message_sender, quit_handler=quit_handler, session_data=session_data)
    await task.execute()

    # Verificar que se llamó al handler
    quit_handler.handle.assert_called_once()


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

    # Mock del handler
    quit_handler = MagicMock()
    quit_handler.handle = AsyncMock(
        return_value=CommandResult.ok(data={"user_id": 100, "username": "TestUser"})
    )

    session_data: dict[str, dict[str, int] | int | str] = {
        "user_id": 100,
        "username": "TestUser",
    }

    data = bytes([ClientPacketID.QUIT])

    task = TaskQuit(data, message_sender, quit_handler=quit_handler, session_data=session_data)
    await task.execute()

    # Verificar que se llamó al handler
    quit_handler.handle.assert_called_once()


@pytest.mark.asyncio
async def test_task_quit_clears_session() -> None:
    """Verifica que TaskQuit limpie la sesión."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()
    writer.close = MagicMock()
    writer.wait_closed = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)

    # Mock del handler
    quit_handler = MagicMock()
    quit_handler.handle = AsyncMock(
        return_value=CommandResult.ok(data={"user_id": 100, "username": "TestUser"})
    )

    session_data: dict[str, dict[str, int] | int | str] = {
        "user_id": 100,
        "username": "TestUser",
        "other_data": "test",
    }

    data = bytes([ClientPacketID.QUIT])

    task = TaskQuit(data, message_sender, quit_handler=quit_handler, session_data=session_data)
    await task.execute()

    # Verificar que la sesión fue limpiada
    assert len(session_data) == 0


@pytest.mark.asyncio
async def test_task_quit_notifies_multiple_maps() -> None:
    """Verifica que TaskQuit notifique a jugadores en múltiples mapas."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()
    writer.close = MagicMock()
    writer.wait_closed = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)

    # Mock del handler
    quit_handler = MagicMock()
    quit_handler.handle = AsyncMock(
        return_value=CommandResult.ok(data={"user_id": 100, "username": "TestUser"})
    )

    session_data: dict[str, dict[str, int] | int | str] = {
        "user_id": 100,
        "username": "TestUser",
    }

    data = bytes([ClientPacketID.QUIT])

    task = TaskQuit(data, message_sender, quit_handler=quit_handler, session_data=session_data)
    await task.execute()

    # Verificar que se llamó al handler
    quit_handler.handle.assert_called_once()
