"""Tests para TaskChangeHeading."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.commands.base import CommandResult
from src.commands.change_heading_command import ChangeHeadingCommand
from src.messaging.message_sender import MessageSender
from src.network.client_connection import ClientConnection
from src.network.packet_id import ClientPacketID
from src.tasks.player.task_change_heading import TaskChangeHeading


@pytest.mark.asyncio
async def test_task_change_heading_success() -> None:
    """Verifica que TaskChangeHeading procese correctamente el cambio de dirección."""
    # Mock del writer
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    # Crear conexión y message sender
    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)

    # Datos de sesión con user_id
    session_data: dict[str, dict[str, int] | int] = {"user_id": 123}

    # Construir paquete CHANGE_HEADING con dirección Este (2)
    heading = 2
    data = bytes([ClientPacketID.CHANGE_HEADING, heading])

    # Mock del handler
    change_heading_handler = MagicMock()
    change_heading_handler.handle = AsyncMock(
        return_value=CommandResult.ok(data={"user_id": 123, "heading": heading})
    )

    # Crear y ejecutar tarea
    task = TaskChangeHeading(
        data,
        message_sender,
        change_heading_handler=change_heading_handler,
        session_data=session_data,
    )
    await task.execute()

    # Verificar que se llamó al handler con el comando correcto
    change_heading_handler.handle.assert_called_once()
    call_args = change_heading_handler.handle.call_args[0][0]
    assert isinstance(call_args, ChangeHeadingCommand)
    assert call_args.user_id == 123
    assert call_args.heading == heading


@pytest.mark.asyncio
async def test_task_change_heading_all_directions() -> None:
    """Verifica que TaskChangeHeading funcione con todas las direcciones."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)

    session_data: dict[str, dict[str, int] | int] = {"user_id": 456}

    # Mock del handler
    change_heading_handler = MagicMock()
    change_heading_handler.handle = AsyncMock(return_value=CommandResult.ok())

    # Probar todas las direcciones: 1=Norte, 2=Este, 3=Sur, 4=Oeste
    for heading in [1, 2, 3, 4]:
        data = bytes([ClientPacketID.CHANGE_HEADING, heading])
        task = TaskChangeHeading(
            data,
            message_sender,
            change_heading_handler=change_heading_handler,
            session_data=session_data,
        )
        await task.execute()

    # Verificar que se llamó 4 veces
    assert change_heading_handler.handle.call_count == 4


@pytest.mark.asyncio
async def test_task_change_heading_invalid_direction() -> None:
    """Verifica que TaskChangeHeading rechace direcciones inválidas."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)

    session_data: dict[str, dict[str, int] | int] = {"user_id": 789}

    # Mock del handler (no debería llamarse si el parsing falla)
    change_heading_handler = MagicMock()
    change_heading_handler.handle = AsyncMock()

    # Probar dirección inválida (5)
    data = bytes([ClientPacketID.CHANGE_HEADING, 5])
    task = TaskChangeHeading(
        data,
        message_sender,
        change_heading_handler=change_heading_handler,
        session_data=session_data,
    )
    await task.execute()

    # Verificar que NO se llamó al handler (parsing falló)
    change_heading_handler.handle.assert_not_called()


@pytest.mark.asyncio
async def test_task_change_heading_no_session() -> None:
    """Verifica que TaskChangeHeading falle sin user_id en sesión."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)

    # Sin session_data
    session_data: dict[str, dict[str, int]] = {}

    data = bytes([ClientPacketID.CHANGE_HEADING, 1])

    # Mock del handler (no debería llamarse si no hay user_id)
    change_heading_handler = MagicMock()
    change_heading_handler.handle = AsyncMock()

    task = TaskChangeHeading(
        data,
        message_sender,
        change_heading_handler=change_heading_handler,
        session_data=session_data,
    )
    await task.execute()

    # Verificar que NO se llamó al handler
    change_heading_handler.handle.assert_not_called()


@pytest.mark.asyncio
async def test_task_change_heading_handler_not_available() -> None:
    """Verifica que TaskChangeHeading maneje cuando el handler no está disponible."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)

    session_data: dict[str, dict[str, int] | int] = {"user_id": 999}

    data = bytes([ClientPacketID.CHANGE_HEADING, 1])

    # Sin handler
    task = TaskChangeHeading(
        data, message_sender, change_heading_handler=None, session_data=session_data
    )
    await task.execute()

    # El test pasa si no hay excepciones (solo se loguea error)


@pytest.mark.asyncio
async def test_task_change_heading_invalid_packet() -> None:
    """Verifica que TaskChangeHeading rechace paquetes inválidos."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)

    session_data: dict[str, dict[str, int] | int] = {"user_id": 111}

    # Paquete demasiado corto
    data = bytes([ClientPacketID.CHANGE_HEADING])

    # Mock del handler (no debería llamarse si el parsing falla)
    change_heading_handler = MagicMock()
    change_heading_handler.handle = AsyncMock()

    task = TaskChangeHeading(
        data,
        message_sender,
        change_heading_handler=change_heading_handler,
        session_data=session_data,
    )

    # Debe lanzar ValueError por packet truncado
    with pytest.raises(ValueError, match="Packet truncado"):
        await task.execute()

    # Verificar que NO se llamó al handler
    change_heading_handler.handle.assert_not_called()
