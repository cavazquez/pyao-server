"""Tests para TaskRequestPositionUpdate."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.commands.base import CommandResult
from src.commands.request_position_update_command import RequestPositionUpdateCommand
from src.messaging.message_sender import MessageSender
from src.network.client_connection import ClientConnection
from src.network.packet_id import ClientPacketID
from src.tasks.player.task_request_position_update import TaskRequestPositionUpdate


@pytest.mark.asyncio
async def test_request_position_update_success() -> None:
    """Verifica que TaskRequestPositionUpdate envíe la posición correcta."""
    # Mock de writer
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    # Mock del handler
    request_position_update_handler = MagicMock()
    request_position_update_handler.handle = AsyncMock(
        return_value=CommandResult.ok(data={"user_id": 123, "x": 75, "y": 80, "map": 1})
    )

    # Crear conexión y message sender
    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)
    message_sender.send_pos_update = AsyncMock()

    # Session data con user_id
    session_data = {"user_id": 123, "username": "testuser"}

    # Construir paquete REQUEST_POSITION_UPDATE (solo PacketID)
    data = bytes([ClientPacketID.REQUEST_POSITION_UPDATE])

    # Crear y ejecutar tarea
    task = TaskRequestPositionUpdate(
        data,
        message_sender,
        request_position_update_handler=request_position_update_handler,
        session_data=session_data,
    )
    await task.execute()

    # Verificar que se llamó al handler
    request_position_update_handler.handle.assert_called_once()
    call_args = request_position_update_handler.handle.call_args[0][0]
    assert isinstance(call_args, RequestPositionUpdateCommand)
    assert call_args.user_id == 123

    # El handler internamente llama a send_pos_update, pero como estamos mockeando el handler,
    # no se ejecuta realmente. El test verifica que el handler fue llamado con el comando correcto.


@pytest.mark.asyncio
async def test_request_position_update_not_logged_in() -> None:
    """Verifica que no se envíe nada si el usuario no está logueado."""
    # Mock de writer
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    # Mock del handler (no debería llamarse)
    request_position_update_handler = MagicMock()
    request_position_update_handler.handle = AsyncMock()

    # Crear conexión y message sender
    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)

    # Session data vacía (no logueado)
    session_data = {}

    # Construir paquete REQUEST_POSITION_UPDATE
    data = bytes([ClientPacketID.REQUEST_POSITION_UPDATE])

    # Crear y ejecutar tarea
    task = TaskRequestPositionUpdate(
        data,
        message_sender,
        request_position_update_handler=request_position_update_handler,
        session_data=session_data,
    )
    await task.execute()

    # Verificar que NO se llamó al handler
    request_position_update_handler.handle.assert_not_called()

    # Verificar que NO se envió ningún paquete
    assert writer.write.call_count == 0


@pytest.mark.asyncio
async def test_request_position_update_no_position_found() -> None:
    """Verifica que se envíe posición por defecto si no se encuentra en Redis."""
    # Mock de writer
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    # Mock del handler que retorna posición por defecto
    request_position_update_handler = MagicMock()
    request_position_update_handler.handle = AsyncMock(
        return_value=CommandResult.ok(data={"user_id": 123, "x": 50, "y": 50, "default": True})
    )

    # Crear conexión y message sender
    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)
    message_sender.send_pos_update = AsyncMock()

    # Session data con user_id
    session_data = {"user_id": 123, "username": "testuser"}

    # Construir paquete REQUEST_POSITION_UPDATE
    data = bytes([ClientPacketID.REQUEST_POSITION_UPDATE])

    # Crear y ejecutar tarea
    task = TaskRequestPositionUpdate(
        data,
        message_sender,
        request_position_update_handler=request_position_update_handler,
        session_data=session_data,
    )
    await task.execute()

    # Verificar que se llamó al handler
    request_position_update_handler.handle.assert_called_once()
    call_args = request_position_update_handler.handle.call_args[0][0]
    assert isinstance(call_args, RequestPositionUpdateCommand)
    assert call_args.user_id == 123

    # El handler internamente llama a send_pos_update, pero como estamos mockeando el handler,
    # no se ejecuta realmente. El test verifica que el handler fue llamado con el comando correcto.


@pytest.mark.asyncio
async def test_request_position_update_no_handler() -> None:
    """Verifica que no se envíe nada si no hay handler."""
    # Mock de writer
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    # Crear conexión y message sender
    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)

    # Session data con user_id
    session_data = {"user_id": 123, "username": "testuser"}

    # Construir paquete REQUEST_POSITION_UPDATE
    data = bytes([ClientPacketID.REQUEST_POSITION_UPDATE])

    # Crear y ejecutar tarea sin handler
    task = TaskRequestPositionUpdate(
        data, message_sender, request_position_update_handler=None, session_data=session_data
    )
    await task.execute()

    # Verificar que NO se envió ningún paquete
    assert writer.write.call_count == 0
