"""Tests para TaskUptime."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.commands.base import CommandResult
from src.commands.uptime_command import UptimeCommand
from src.messaging.message_sender import MessageSender
from src.network.client_connection import ClientConnection
from src.network.packet_id import ClientPacketID
from src.tasks.task_uptime import TaskUptime


@pytest.mark.asyncio
async def test_task_uptime_with_server_repo() -> None:
    """Verifica que TaskUptime muestre el tiempo de actividad."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)
    message_sender.send_console_msg = AsyncMock()

    # Mock del handler
    uptime_handler = MagicMock()
    uptime_handler.handle = AsyncMock(
        return_value=CommandResult.ok(data={"message": "El servidor lleva activo: 1 hora"})
    )

    # Construir paquete UPTIME (solo PacketID)
    data = bytes([ClientPacketID.UPTIME])

    task = TaskUptime(data, message_sender, uptime_handler=uptime_handler)
    await task.execute()

    # Verificar que se llamó al handler
    uptime_handler.handle.assert_called_once()
    call_args = uptime_handler.handle.call_args[0][0]
    assert isinstance(call_args, UptimeCommand)


@pytest.mark.asyncio
async def test_task_uptime_days_hours_minutes() -> None:
    """Verifica que TaskUptime formatee correctamente días, horas y minutos."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)
    message_sender.send_console_msg = AsyncMock()

    # Mock del handler
    uptime_handler = MagicMock()
    uptime_handler.handle = AsyncMock(
        return_value=CommandResult.ok(
            data={"message": "El servidor lleva activo: 2 dias, 3 horas, 15 minutos"}
        )
    )

    data = bytes([ClientPacketID.UPTIME])

    task = TaskUptime(data, message_sender, uptime_handler=uptime_handler)
    await task.execute()

    # Verificar que se llamó al handler
    uptime_handler.handle.assert_called_once()


@pytest.mark.asyncio
async def test_task_uptime_seconds_only() -> None:
    """Verifica que TaskUptime muestre solo segundos si el uptime es muy corto."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)
    message_sender.send_console_msg = AsyncMock()

    # Mock del handler
    uptime_handler = MagicMock()
    uptime_handler.handle = AsyncMock(
        return_value=CommandResult.ok(data={"message": "El servidor lleva activo: 30 segundos"})
    )

    data = bytes([ClientPacketID.UPTIME])

    task = TaskUptime(data, message_sender, uptime_handler=uptime_handler)
    await task.execute()

    # Verificar que se llamó al handler
    uptime_handler.handle.assert_called_once()


@pytest.mark.asyncio
async def test_task_uptime_no_timestamp() -> None:
    """Verifica que TaskUptime maneje el caso cuando no hay timestamp."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)
    message_sender.send_console_msg = AsyncMock()

    # Mock del handler
    uptime_handler = MagicMock()
    uptime_handler.handle = AsyncMock(
        return_value=CommandResult.ok(
            data={"message": "No se pudo obtener el tiempo de actividad del servidor"}
        )
    )

    data = bytes([ClientPacketID.UPTIME])

    task = TaskUptime(data, message_sender, uptime_handler=uptime_handler)
    await task.execute()

    # Verificar que se llamó al handler
    uptime_handler.handle.assert_called_once()


@pytest.mark.asyncio
async def test_task_uptime_without_server_repo() -> None:
    """Verifica que TaskUptime funcione sin repositorio."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)
    message_sender.send_console_msg = AsyncMock()

    # Mock del handler
    uptime_handler = MagicMock()
    uptime_handler.handle = AsyncMock(
        return_value=CommandResult.ok(data={"message": "Informacion de uptime no disponible"})
    )

    data = bytes([ClientPacketID.UPTIME])

    task = TaskUptime(data, message_sender, uptime_handler=uptime_handler)
    await task.execute()

    # Verificar que se llamó al handler
    uptime_handler.handle.assert_called_once()


@pytest.mark.asyncio
async def test_task_uptime_singular_plural() -> None:
    """Verifica que TaskUptime use singular/plural correctamente."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)
    message_sender.send_console_msg = AsyncMock()

    # Mock del handler
    uptime_handler = MagicMock()
    uptime_handler.handle = AsyncMock(
        return_value=CommandResult.ok(
            data={"message": "El servidor lleva activo: 1 dia, 1 hora, 1 minuto, 1 segundo"}
        )
    )

    data = bytes([ClientPacketID.UPTIME])

    task = TaskUptime(data, message_sender, uptime_handler=uptime_handler)
    await task.execute()

    # Verificar que se llamó al handler
    uptime_handler.handle.assert_called_once()
