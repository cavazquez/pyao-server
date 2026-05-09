"""Tests para TaskWhisper."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.commands.base import CommandResult
from src.commands.whisper_command import WhisperCommand
from src.messaging.message_sender import MessageSender
from src.network.client_connection import ClientConnection
from src.network.packet_id import ClientPacketID
from src.tasks.interaction.task_whisper import TaskWhisper


@pytest.mark.asyncio
async def test_task_whisper_success() -> None:
    """Verifica que TaskWhisper procese correctamente un mensaje susurrado."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)

    session_data: dict[str, dict[str, int]] = {"user_id": 123}

    receiver = "destino"
    message = "Hola"
    receiver_bytes = receiver.encode("utf-8")
    message_bytes = message.encode("utf-8")
    receiver_len = len(receiver_bytes)
    message_len = len(message_bytes)
    data = (
        bytes([ClientPacketID.WHISPER])
        + receiver_len.to_bytes(2, byteorder="little")
        + receiver_bytes
        + message_len.to_bytes(2, byteorder="little")
        + message_bytes
    )

    whisper_handler = MagicMock()
    whisper_handler.handle = AsyncMock(return_value=CommandResult.ok())

    task = TaskWhisper(data, message_sender, whisper_handler=whisper_handler, session_data=session_data)
    await task.execute()

    whisper_handler.handle.assert_called_once()
    call_args = whisper_handler.handle.call_args[0][0]
    assert isinstance(call_args, WhisperCommand)
    assert call_args.user_id == 123
    assert call_args.receiver == receiver
    assert call_args.message == message


@pytest.mark.asyncio
async def test_task_whisper_empty_receiver() -> None:
    """Verifica que TaskWhisper rechace mensajes con receptor vacío."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)

    session_data: dict[str, dict[str, int]] = {"user_id": 123}

    receiver = ""
    message = "Hola"
    receiver_bytes = receiver.encode("utf-8")
    message_bytes = message.encode("utf-8")
    receiver_len = len(receiver_bytes)
    message_len = len(message_bytes)
    data = (
        bytes([ClientPacketID.WHISPER])
        + receiver_len.to_bytes(2, byteorder="little")
        + receiver_bytes
        + message_len.to_bytes(2, byteorder="little")
        + message_bytes
    )

    whisper_handler = MagicMock()
    whisper_handler.handle = AsyncMock()

    task = TaskWhisper(data, message_sender, whisper_handler=whisper_handler, session_data=session_data)
    await task.execute()

    whisper_handler.handle.assert_not_called()


@pytest.mark.asyncio
async def test_task_whisper_empty_message() -> None:
    """Verifica que TaskWhisper rechace mensajes con mensaje vacío."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)

    session_data: dict[str, dict[str, int]] = {"user_id": 123}

    receiver = "destino"
    message = ""
    receiver_bytes = receiver.encode("utf-8")
    message_bytes = message.encode("utf-8")
    receiver_len = len(receiver_bytes)
    message_len = len(message_bytes)
    data = (
        bytes([ClientPacketID.WHISPER])
        + receiver_len.to_bytes(2, byteorder="little")
        + receiver_bytes
        + message_len.to_bytes(2, byteorder="little")
        + message_bytes
    )

    whisper_handler = MagicMock()
    whisper_handler.handle = AsyncMock()

    task = TaskWhisper(data, message_sender, whisper_handler=whisper_handler, session_data=session_data)
    await task.execute()

    whisper_handler.handle.assert_not_called()


@pytest.mark.asyncio
async def test_task_whisper_no_session() -> None:
    """Verifica que TaskWhisper falle sin sesión activa."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)

    session_data: dict[str, dict[str, int]] = {}

    receiver = "destino"
    message = "Hola"
    receiver_bytes = receiver.encode("utf-8")
    message_bytes = message.encode("utf-8")
    receiver_len = len(receiver_bytes)
    message_len = len(message_bytes)
    data = (
        bytes([ClientPacketID.WHISPER])
        + receiver_len.to_bytes(2, byteorder="little")
        + receiver_bytes
        + message_len.to_bytes(2, byteorder="little")
        + message_bytes
    )

    whisper_handler = MagicMock()
    whisper_handler.handle = AsyncMock()

    task = TaskWhisper(data, message_sender, whisper_handler=whisper_handler, session_data=session_data)
    await task.execute()

    whisper_handler.handle.assert_not_called()


@pytest.mark.asyncio
async def test_task_whisper_handler_not_available() -> None:
    """Verifica que TaskWhisper maneje cuando el handler no está disponible."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)

    session_data: dict[str, dict[str, int]] = {"user_id": 123}

    receiver = "destino"
    message = "Hola"
    receiver_bytes = receiver.encode("utf-8")
    message_bytes = message.encode("utf-8")
    receiver_len = len(receiver_bytes)
    message_len = len(message_bytes)
    data = (
        bytes([ClientPacketID.WHISPER])
        + receiver_len.to_bytes(2, byteorder="little")
        + receiver_bytes
        + message_len.to_bytes(2, byteorder="little")
        + message_bytes
    )

    task = TaskWhisper(data, message_sender, whisper_handler=None, session_data=session_data)
    await task.execute()


@pytest.mark.asyncio
async def test_task_whisper_unicode() -> None:
    """Verifica que TaskWhisper maneje correctamente mensajes Unicode."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)

    session_data: dict[str, dict[str, int]] = {"user_id": 123}

    receiver = "用户"
    message = "你好"
    receiver_bytes = receiver.encode("utf-8")
    message_bytes = message.encode("utf-8")
    receiver_len = len(receiver_bytes)
    message_len = len(message_bytes)
    data = (
        bytes([ClientPacketID.WHISPER])
        + receiver_len.to_bytes(2, byteorder="little")
        + receiver_bytes
        + message_len.to_bytes(2, byteorder="little")
        + message_bytes
    )

    whisper_handler = MagicMock()
    whisper_handler.handle = AsyncMock(return_value=CommandResult.ok())

    task = TaskWhisper(data, message_sender, whisper_handler=whisper_handler, session_data=session_data)
    await task.execute()

    whisper_handler.handle.assert_called_once()
    call_args = whisper_handler.handle.call_args[0][0]
    assert call_args.receiver == receiver
    assert call_args.message == message


@pytest.mark.asyncio
async def test_task_whisper_long_receiver() -> None:
    """Verifica que TaskWhisper maneje correctamente receptor largo."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)

    session_data: dict[str, dict[str, int]] = {"user_id": 123}

    receiver = "a" * 20
    message = "Hola"
    receiver_bytes = receiver.encode("utf-8")
    message_bytes = message.encode("utf-8")
    receiver_len = len(receiver_bytes)
    message_len = len(message_bytes)
    data = (
        bytes([ClientPacketID.WHISPER])
        + receiver_len.to_bytes(2, byteorder="little")
        + receiver_bytes
        + message_len.to_bytes(2, byteorder="little")
        + message_bytes
    )

    whisper_handler = MagicMock()
    whisper_handler.handle = AsyncMock(return_value=CommandResult.ok())

    task = TaskWhisper(data, message_sender, whisper_handler=whisper_handler, session_data=session_data)
    await task.execute()

    whisper_handler.handle.assert_called_once()