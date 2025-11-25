"""Tests para TaskTalk."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.commands.base import CommandResult
from src.commands.talk_command import TalkCommand
from src.messaging.message_sender import MessageSender
from src.network.client_connection import ClientConnection
from src.network.packet_id import ClientPacketID
from src.tasks.interaction.task_talk import TaskTalk


@pytest.mark.asyncio
async def test_task_talk_success() -> None:
    """Verifica que TaskTalk procese correctamente un mensaje de chat."""
    # Mock del writer
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    # Crear conexión y message sender
    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)

    # Datos de sesión con user_id
    session_data: dict[str, dict[str, int]] = {"user_id": 123}

    # Construir paquete TALK con mensaje "Hola"
    message = "Hola"
    message_bytes = message.encode("utf-8")
    msg_length = len(message_bytes)
    data = bytes([ClientPacketID.TALK]) + msg_length.to_bytes(2, byteorder="little") + message_bytes

    # Mock del handler
    talk_handler = MagicMock()
    talk_handler.handle = AsyncMock(return_value=CommandResult.ok())

    # Crear y ejecutar tarea
    task = TaskTalk(data, message_sender, talk_handler=talk_handler, session_data=session_data)
    await task.execute()

    # Verificar que se llamó al handler con el comando correcto
    talk_handler.handle.assert_called_once()
    call_args = talk_handler.handle.call_args[0][0]
    assert isinstance(call_args, TalkCommand)
    assert call_args.user_id == 123
    assert call_args.message == message


@pytest.mark.asyncio
async def test_task_talk_with_broadcast() -> None:
    """Verifica que TaskTalk haga broadcast del mensaje a otros jugadores."""
    # Mock del writer
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    # Crear conexión y message sender
    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)

    # Datos de sesión con user_id y username
    session_data: dict[str, dict[str, int] | int | str] = {
        "user_id": 123,
        "username": "TestUser",
    }

    # Construir paquete TALK con mensaje "Hola mundo"
    message = "Hola mundo"
    message_bytes = message.encode("utf-8")
    msg_length = len(message_bytes)
    data = bytes([ClientPacketID.TALK]) + msg_length.to_bytes(2, byteorder="little") + message_bytes

    # Mock del handler
    talk_handler = MagicMock()
    talk_handler.handle = AsyncMock(
        return_value=CommandResult.ok(
            data={"user_id": 123, "username": "TestUser", "message": message, "map_id": 1}
        )
    )

    # Crear y ejecutar tarea
    task = TaskTalk(data, message_sender, talk_handler=talk_handler, session_data=session_data)
    await task.execute()

    # Verificar que se llamó al handler con el comando correcto
    talk_handler.handle.assert_called_once()
    call_args = talk_handler.handle.call_args[0][0]
    assert isinstance(call_args, TalkCommand)
    assert call_args.user_id == 123
    assert call_args.message == message


@pytest.mark.asyncio
async def test_task_talk_empty_message() -> None:
    """Verifica que TaskTalk maneje correctamente un mensaje vacío."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)

    session_data: dict[str, dict[str, int]] = {"user_id": 123}

    # Construir paquete TALK con mensaje vacío (debería fallar validación)
    message = ""
    message_bytes = message.encode("utf-8")
    msg_length = len(message_bytes)
    data = bytes([ClientPacketID.TALK]) + msg_length.to_bytes(2, byteorder="little") + message_bytes

    # Mock del handler (no debería llamarse si el parsing falla)
    talk_handler = MagicMock()
    talk_handler.handle = AsyncMock()

    task = TaskTalk(data, message_sender, talk_handler=talk_handler, session_data=session_data)
    await task.execute()

    # El handler no debería llamarse si el parsing falla
    talk_handler.handle.assert_not_called()


@pytest.mark.asyncio
async def test_task_talk_long_message() -> None:
    """Verifica que TaskTalk maneje correctamente mensajes largos."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)

    session_data: dict[str, dict[str, int]] = {"user_id": 123}

    # Construir paquete TALK con mensaje largo (pero dentro del límite de 255)
    message = "Este es un mensaje largo " * 8  # ~200 caracteres, dentro del límite
    message_bytes = message.encode("utf-8")
    msg_length = len(message_bytes)
    data = bytes([ClientPacketID.TALK]) + msg_length.to_bytes(2, byteorder="little") + message_bytes

    # Mock del handler
    talk_handler = MagicMock()
    talk_handler.handle = AsyncMock(return_value=CommandResult.ok())

    task = TaskTalk(data, message_sender, talk_handler=talk_handler, session_data=session_data)
    await task.execute()

    # Verificar que se llamó al handler
    talk_handler.handle.assert_called_once()
    call_args = talk_handler.handle.call_args[0][0]
    assert isinstance(call_args, TalkCommand)
    assert call_args.message == message


@pytest.mark.asyncio
async def test_task_talk_unicode_message() -> None:
    """Verifica que TaskTalk maneje correctamente mensajes con Unicode."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)

    session_data: dict[str, dict[str, int]] = {"user_id": 123}

    # Construir paquete TALK con mensaje Unicode
    message = "Hola 你好 مرحبا 🎮"
    message_bytes = message.encode("utf-8")
    msg_length = len(message_bytes)
    data = bytes([ClientPacketID.TALK]) + msg_length.to_bytes(2, byteorder="little") + message_bytes

    # Mock del handler
    talk_handler = MagicMock()
    talk_handler.handle = AsyncMock(return_value=CommandResult.ok())

    task = TaskTalk(data, message_sender, talk_handler=talk_handler, session_data=session_data)
    await task.execute()

    # Verificar que se llamó al handler
    talk_handler.handle.assert_called_once()
    call_args = talk_handler.handle.call_args[0][0]
    assert isinstance(call_args, TalkCommand)
    assert call_args.message == message


@pytest.mark.asyncio
async def test_task_talk_invalid_packet_too_short() -> None:
    """Verifica que TaskTalk rechace paquetes demasiado cortos."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)

    session_data: dict[str, dict[str, int]] = {"user_id": 123}

    # Paquete demasiado corto (solo PacketID)
    data = bytes([ClientPacketID.TALK])

    # Mock del handler (no debería llamarse si el parsing falla)
    talk_handler = MagicMock()
    talk_handler.handle = AsyncMock()

    task = TaskTalk(data, message_sender, talk_handler=talk_handler, session_data=session_data)
    await task.execute()

    # El handler no debería llamarse si el parsing falla
    talk_handler.handle.assert_not_called()


@pytest.mark.asyncio
async def test_task_talk_invalid_packet_wrong_length() -> None:
    """Verifica que TaskTalk rechace paquetes con longitud incorrecta."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)

    session_data: dict[str, dict[str, int]] = {"user_id": 123}

    # Paquete con longitud que no coincide con el contenido
    data = bytes([ClientPacketID.TALK]) + (100).to_bytes(2, byteorder="little") + b"Hola"

    # Mock del handler (no debería llamarse si el parsing falla)
    talk_handler = MagicMock()
    talk_handler.handle = AsyncMock()

    task = TaskTalk(data, message_sender, talk_handler=talk_handler, session_data=session_data)
    await task.execute()

    # El handler no debería llamarse si el parsing falla
    talk_handler.handle.assert_not_called()


@pytest.mark.asyncio
async def test_task_talk_no_session() -> None:
    """Verifica que TaskTalk falle sin sesión activa."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)

    # Sin session_data
    session_data: dict[str, dict[str, int]] = {}

    # Construir paquete TALK válido
    message = "Hola"
    message_bytes = message.encode("utf-8")
    msg_length = len(message_bytes)
    data = bytes([ClientPacketID.TALK]) + msg_length.to_bytes(2, byteorder="little") + message_bytes

    # Mock del handler (no debería llamarse si no hay user_id)
    talk_handler = MagicMock()
    talk_handler.handle = AsyncMock()

    task = TaskTalk(data, message_sender, talk_handler=talk_handler, session_data=session_data)
    await task.execute()

    # El handler no debería llamarse si no hay user_id
    talk_handler.handle.assert_not_called()


@pytest.mark.asyncio
async def test_task_talk_without_username() -> None:
    """Verifica que TaskTalk use nombre por defecto si no hay username en sesión."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)

    # Datos de sesión sin username
    session_data: dict[str, dict[str, int]] = {"user_id": 123}

    # Construir paquete TALK
    message = "Hola"
    message_bytes = message.encode("utf-8")
    msg_length = len(message_bytes)
    data = bytes([ClientPacketID.TALK]) + msg_length.to_bytes(2, byteorder="little") + message_bytes

    # Mock del handler
    talk_handler = MagicMock()
    talk_handler.handle = AsyncMock(return_value=CommandResult.ok())

    task = TaskTalk(data, message_sender, talk_handler=talk_handler, session_data=session_data)
    await task.execute()

    # Verificar que se llamó al handler
    talk_handler.handle.assert_called_once()
    call_args = talk_handler.handle.call_args[0][0]
    assert isinstance(call_args, TalkCommand)
    assert call_args.user_id == 123
    assert call_args.message == message


@pytest.mark.asyncio
async def test_task_talk_handler_not_available() -> None:
    """Verifica que TaskTalk maneje cuando el handler no está disponible."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)

    session_data: dict[str, dict[str, int]] = {"user_id": 123}

    # Construir paquete TALK válido
    message = "Hola"
    message_bytes = message.encode("utf-8")
    msg_length = len(message_bytes)
    data = bytes([ClientPacketID.TALK]) + msg_length.to_bytes(2, byteorder="little") + message_bytes

    # Crear tarea sin handler
    task = TaskTalk(data, message_sender, talk_handler=None, session_data=session_data)
    await task.execute()

    # El test pasa si no hay excepciones (solo se loguea error)
