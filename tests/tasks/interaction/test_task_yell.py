"""Tests para TaskYell."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.commands.base import CommandResult
from src.commands.yell_command import YellCommand
from src.messaging.message_sender import MessageSender
from src.network.client_connection import ClientConnection
from src.network.packet_id import ClientPacketID
from src.tasks.interaction.task_yell import TaskYell


@pytest.mark.asyncio
async def test_task_yell_success() -> None:
    """Verifica que TaskYell procese correctamente un mensaje de grito."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)

    session_data: dict[str, dict[str, int]] = {"user_id": 123}

    message = "Hola"
    message_bytes = message.encode("utf-8")
    msg_length = len(message_bytes)
    data = bytes([ClientPacketID.YELL]) + msg_length.to_bytes(2, byteorder="little") + message_bytes

    yell_handler = MagicMock()
    yell_handler.handle = AsyncMock(return_value=CommandResult.ok())

    task = TaskYell(data, message_sender, yell_handler=yell_handler, session_data=session_data)
    await task.execute()

    yell_handler.handle.assert_called_once()
    call_args = yell_handler.handle.call_args[0][0]
    assert isinstance(call_args, YellCommand)
    assert call_args.user_id == 123
    assert call_args.message == message


@pytest.mark.asyncio
async def test_task_yell_long_message() -> None:
    """Verifica que TaskYell maneje correctamente mensajes largos."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)

    session_data: dict[str, dict[str, int]] = {"user_id": 123}

    message = "Grito largo " * 10
    message_bytes = message.encode("utf-8")
    msg_length = len(message_bytes)
    data = bytes([ClientPacketID.YELL]) + msg_length.to_bytes(2, byteorder="little") + message_bytes

    yell_handler = MagicMock()
    yell_handler.handle = AsyncMock(return_value=CommandResult.ok())

    task = TaskYell(data, message_sender, yell_handler=yell_handler, session_data=session_data)
    await task.execute()

    yell_handler.handle.assert_called_once()


@pytest.mark.asyncio
async def test_task_yell_empty_message() -> None:
    """Verifica que TaskYell rechace mensajes vacíos."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)

    session_data: dict[str, dict[str, int]] = {"user_id": 123}

    message = ""
    message_bytes = message.encode("utf-8")
    msg_length = len(message_bytes)
    data = bytes([ClientPacketID.YELL]) + msg_length.to_bytes(2, byteorder="little") + message_bytes

    yell_handler = MagicMock()
    yell_handler.handle = AsyncMock()

    task = TaskYell(data, message_sender, yell_handler=yell_handler, session_data=session_data)
    await task.execute()

    yell_handler.handle.assert_not_called()


@pytest.mark.asyncio
async def test_task_yell_no_session() -> None:
    """Verifica que TaskYell falle sin sesión activa."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)

    session_data: dict[str, dict[str, int]] = {}

    message = "Hola"
    message_bytes = message.encode("utf-8")
    msg_length = len(message_bytes)
    data = bytes([ClientPacketID.YELL]) + msg_length.to_bytes(2, byteorder="little") + message_bytes

    yell_handler = MagicMock()
    yell_handler.handle = AsyncMock()

    task = TaskYell(data, message_sender, yell_handler=yell_handler, session_data=session_data)
    await task.execute()

    yell_handler.handle.assert_not_called()


@pytest.mark.asyncio
async def test_task_yell_handler_not_available() -> None:
    """Verifica que TaskYell maneje cuando el handler no está disponible."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)

    session_data: dict[str, dict[str, int]] = {"user_id": 123}

    message = "Hola"
    message_bytes = message.encode("utf-8")
    msg_length = len(message_bytes)
    data = bytes([ClientPacketID.YELL]) + msg_length.to_bytes(2, byteorder="little") + message_bytes

    task = TaskYell(data, message_sender, yell_handler=None, session_data=session_data)
    await task.execute()


@pytest.mark.asyncio
async def test_task_yell_unicode() -> None:
    """Verifica que TaskYell maneje correctamente mensajes Unicode."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)

    session_data: dict[str, dict[str, int]] = {"user_id": 123}

    message = " Gritó 你好"
    message_bytes = message.encode("utf-8")
    msg_length = len(message_bytes)
    data = bytes([ClientPacketID.YELL]) + msg_length.to_bytes(2, byteorder="little") + message_bytes

    yell_handler = MagicMock()
    yell_handler.handle = AsyncMock(return_value=CommandResult.ok())

    task = TaskYell(data, message_sender, yell_handler=yell_handler, session_data=session_data)
    await task.execute()

    yell_handler.handle.assert_called_once()
    call_args = yell_handler.handle.call_args[0][0]
    assert call_args.message == message