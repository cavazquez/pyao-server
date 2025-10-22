"""Tests para TaskTalk."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.network.client_connection import ClientConnection
from src.messaging.message_sender import MessageSender
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

    # Crear y ejecutar tarea (sin repos para test simple)
    task = TaskTalk(data, message_sender, None, None, None, session_data)
    await task.execute()

    # El test pasa si no hay excepciones
    # En un test completo verificaríamos que se envió el mensaje a otros jugadores


@pytest.mark.asyncio
async def test_task_talk_with_broadcast() -> None:
    """Verifica que TaskTalk haga broadcast del mensaje a otros jugadores."""
    # Mock del writer
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    # Mock del player_repo
    player_repo = MagicMock()
    player_repo.get_position = AsyncMock(return_value={"x": 50, "y": 50, "map": 1})

    # Mock del account_repo
    account_repo = MagicMock()

    # Mock del map_manager
    map_manager = MagicMock()
    # Simular que hay 2 jugadores en el mapa
    other_sender1 = MagicMock()
    other_sender1.send_console_msg = AsyncMock()
    other_sender2 = MagicMock()
    other_sender2.send_console_msg = AsyncMock()
    map_manager.get_all_message_senders_in_map.return_value = [other_sender1, other_sender2]

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

    # Crear y ejecutar tarea
    task = TaskTalk(
        data,
        message_sender,
        player_repo,
        account_repo,
        map_manager,
        session_data,
    )
    await task.execute()

    # Verificar que se llamó a get_position
    player_repo.get_position.assert_called_once_with(123)

    # Verificar que se llamó a get_all_message_senders_in_map
    map_manager.get_all_message_senders_in_map.assert_called_once_with(1)

    # Verificar que se envió el mensaje a ambos jugadores
    other_sender1.send_console_msg.assert_called_once_with("TestUser: Hola mundo")
    other_sender2.send_console_msg.assert_called_once_with("TestUser: Hola mundo")


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

    # Construir paquete TALK con mensaje vacío
    message = ""
    message_bytes = message.encode("utf-8")
    msg_length = len(message_bytes)
    data = bytes([ClientPacketID.TALK]) + msg_length.to_bytes(2, byteorder="little") + message_bytes

    task = TaskTalk(data, message_sender, None, None, None, session_data)
    await task.execute()

    # El test pasa si no hay excepciones


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

    # Construir paquete TALK con mensaje largo
    message = "Este es un mensaje muy largo " * 10
    message_bytes = message.encode("utf-8")
    msg_length = len(message_bytes)
    data = bytes([ClientPacketID.TALK]) + msg_length.to_bytes(2, byteorder="little") + message_bytes

    task = TaskTalk(data, message_sender, None, None, None, session_data)
    await task.execute()

    # El test pasa si no hay excepciones


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

    task = TaskTalk(data, message_sender, None, None, None, session_data)
    await task.execute()

    # El test pasa si no hay excepciones


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

    task = TaskTalk(data, message_sender, None, None, None, session_data)
    await task.execute()

    # El test pasa si no hay excepciones (solo se loguea warning)


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

    task = TaskTalk(data, message_sender, None, None, None, session_data)
    await task.execute()

    # El test pasa si no hay excepciones (solo se loguea warning)


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

    task = TaskTalk(data, message_sender, None, None, None, session_data)
    await task.execute()

    # El test pasa si no hay excepciones (solo se loguea warning)


@pytest.mark.asyncio
async def test_task_talk_without_username() -> None:
    """Verifica que TaskTalk use nombre por defecto si no hay username en sesión."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    # Mock del player_repo
    player_repo = MagicMock()
    player_repo.get_position = AsyncMock(return_value={"x": 50, "y": 50, "map": 1})

    # Mock del account_repo
    account_repo = MagicMock()

    # Mock del map_manager
    map_manager = MagicMock()
    other_sender = MagicMock()
    other_sender.send_console_msg = AsyncMock()
    map_manager.get_all_message_senders_in_map.return_value = [other_sender]

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

    task = TaskTalk(data, message_sender, player_repo, account_repo, map_manager, session_data)
    await task.execute()

    # Verificar que se usó "Desconocido" como nombre
    other_sender.send_console_msg.assert_called_once_with("Desconocido: Hola")
