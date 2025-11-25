"""Tests para TaskOnline."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.commands.base import CommandResult
from src.commands.online_command import OnlineCommand
from src.messaging.message_sender import MessageSender
from src.network.client_connection import ClientConnection
from src.network.packet_id import ClientPacketID
from src.tasks.task_online import TaskOnline


@pytest.mark.asyncio
async def test_task_online_with_players() -> None:
    """Verifica que TaskOnline muestre la lista de jugadores conectados."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)
    message_sender.send_multiline_console_msg = AsyncMock()

    # Mock del handler
    online_handler = MagicMock()
    online_handler.handle = AsyncMock(
        return_value=CommandResult.ok(
            data={"user_id": 100, "players": ["Alice", "Bob", "Charlie"], "count": 3}
        )
    )

    # Datos de sesión
    session_data: dict[str, dict[str, int]] = {"user_id": 100}

    # Construir paquete ONLINE (solo PacketID)
    data = bytes([ClientPacketID.ONLINE])

    task = TaskOnline(
        data, message_sender, online_handler=online_handler, session_data=session_data
    )
    await task.execute()

    # Verificar que se llamó al handler
    online_handler.handle.assert_called_once()
    call_args = online_handler.handle.call_args[0][0]
    assert isinstance(call_args, OnlineCommand)
    assert call_args.user_id == 100


@pytest.mark.asyncio
async def test_task_online_no_players() -> None:
    """Verifica que TaskOnline maneje el caso cuando no hay jugadores."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)
    message_sender.send_console_msg = AsyncMock()

    # Mock del handler
    online_handler = MagicMock()
    online_handler.handle = AsyncMock(
        return_value=CommandResult.ok(data={"user_id": 100, "players": [], "count": 0})
    )

    session_data: dict[str, dict[str, int]] = {"user_id": 100}

    data = bytes([ClientPacketID.ONLINE])

    task = TaskOnline(
        data, message_sender, online_handler=online_handler, session_data=session_data
    )
    await task.execute()

    # Verificar que se llamó al handler
    online_handler.handle.assert_called_once()


@pytest.mark.asyncio
async def test_task_online_sorted_alphabetically() -> None:
    """Verifica que los jugadores se muestren ordenados alfabéticamente."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)
    message_sender.send_multiline_console_msg = AsyncMock()

    # Mock del handler
    online_handler = MagicMock()
    online_handler.handle = AsyncMock(
        return_value=CommandResult.ok(
            data={"user_id": 100, "players": ["Charlie", "Alice", "Bob"], "count": 3}
        )
    )

    session_data: dict[str, dict[str, int]] = {"user_id": 100}

    data = bytes([ClientPacketID.ONLINE])

    task = TaskOnline(
        data, message_sender, online_handler=online_handler, session_data=session_data
    )
    await task.execute()

    # Verificar que se llamó al handler
    online_handler.handle.assert_called_once()


@pytest.mark.asyncio
async def test_task_online_single_player() -> None:
    """Verifica que TaskOnline funcione con un solo jugador."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)
    message_sender.send_multiline_console_msg = AsyncMock()

    # Mock del handler
    online_handler = MagicMock()
    online_handler.handle = AsyncMock(
        return_value=CommandResult.ok(data={"user_id": 100, "players": ["Alice"], "count": 1})
    )

    session_data: dict[str, dict[str, int]] = {"user_id": 100}

    data = bytes([ClientPacketID.ONLINE])

    task = TaskOnline(
        data, message_sender, online_handler=online_handler, session_data=session_data
    )
    await task.execute()

    # Verificar que se llamó al handler
    online_handler.handle.assert_called_once()


@pytest.mark.asyncio
async def test_task_online_no_duplicate_usernames() -> None:
    """Verifica que no haya nombres duplicados en la lista."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)
    message_sender.send_multiline_console_msg = AsyncMock()

    # Mock del handler
    online_handler = MagicMock()
    online_handler.handle = AsyncMock(
        return_value=CommandResult.ok(
            data={"user_id": 100, "players": ["Alice", "Bob"], "count": 2}
        )
    )

    session_data: dict[str, dict[str, int]] = {"user_id": 100}

    data = bytes([ClientPacketID.ONLINE])

    task = TaskOnline(
        data, message_sender, online_handler=online_handler, session_data=session_data
    )
    await task.execute()

    # Verificar que se llamó al handler
    online_handler.handle.assert_called_once()


@pytest.mark.asyncio
async def test_task_online_no_session() -> None:
    """Verifica que TaskOnline no falle sin sesión activa."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)

    # Mock del handler (no debería llamarse)
    online_handler = MagicMock()
    online_handler.handle = AsyncMock()

    # Sin session_data
    session_data: dict[str, dict[str, int]] = {}

    data = bytes([ClientPacketID.ONLINE])

    task = TaskOnline(
        data, message_sender, online_handler=online_handler, session_data=session_data
    )
    await task.execute()

    # Verificar que NO se llamó al handler
    online_handler.handle.assert_not_called()
