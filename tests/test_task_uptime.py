"""Tests para TaskUptime."""

import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.client_connection import ClientConnection
from src.messaging.message_sender import MessageSender
from src.packet_id import ClientPacketID
from src.task_uptime import TaskUptime


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

    # Mock del server_repo con timestamp de hace 1 hora
    server_repo = MagicMock()
    current_time = int(time.time())
    one_hour_ago = current_time - 3600
    server_repo.get_uptime_start = AsyncMock(return_value=one_hour_ago)

    # Construir paquete UPTIME (solo PacketID)
    data = bytes([ClientPacketID.UPTIME])

    task = TaskUptime(data, message_sender, server_repo)
    await task.execute()

    # Verificar que se obtuvo el timestamp
    server_repo.get_uptime_start.assert_called_once()

    # Verificar que se envió el mensaje
    message_sender.send_console_msg.assert_called_once()
    sent_message = message_sender.send_console_msg.call_args[0][0]

    assert "El servidor lleva activo:" in sent_message
    assert "1 hora" in sent_message


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

    # Mock del server_repo con timestamp de hace 2 días, 3 horas, 15 minutos
    server_repo = MagicMock()
    current_time = int(time.time())
    uptime_seconds = (2 * 86400) + (3 * 3600) + (15 * 60)  # 2 días, 3 horas, 15 minutos
    start_time = current_time - uptime_seconds
    server_repo.get_uptime_start = AsyncMock(return_value=start_time)

    data = bytes([ClientPacketID.UPTIME])

    task = TaskUptime(data, message_sender, server_repo)
    await task.execute()

    sent_message = message_sender.send_console_msg.call_args[0][0]

    assert "2 dias" in sent_message
    assert "3 horas" in sent_message
    assert "15 minutos" in sent_message


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

    # Mock del server_repo con timestamp de hace 30 segundos
    server_repo = MagicMock()
    current_time = int(time.time())
    start_time = current_time - 30
    server_repo.get_uptime_start = AsyncMock(return_value=start_time)

    data = bytes([ClientPacketID.UPTIME])

    task = TaskUptime(data, message_sender, server_repo)
    await task.execute()

    sent_message = message_sender.send_console_msg.call_args[0][0]

    assert "30 segundos" in sent_message
    assert "minuto" not in sent_message
    assert "hora" not in sent_message


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

    # Mock del server_repo sin timestamp
    server_repo = MagicMock()
    server_repo.get_uptime_start = AsyncMock(return_value=None)

    data = bytes([ClientPacketID.UPTIME])

    task = TaskUptime(data, message_sender, server_repo)
    await task.execute()

    sent_message = message_sender.send_console_msg.call_args[0][0]

    assert "No se pudo obtener" in sent_message


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

    # Sin server_repo
    data = bytes([ClientPacketID.UPTIME])

    task = TaskUptime(data, message_sender, None)
    await task.execute()

    sent_message = message_sender.send_console_msg.call_args[0][0]

    assert "no disponible" in sent_message


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

    # Mock del server_repo con timestamp de hace 1 día, 1 hora, 1 minuto, 1 segundo
    server_repo = MagicMock()
    current_time = int(time.time())
    uptime_seconds = 86400 + 3600 + 60 + 1  # 1 día, 1 hora, 1 minuto, 1 segundo
    start_time = current_time - uptime_seconds
    server_repo.get_uptime_start = AsyncMock(return_value=start_time)

    data = bytes([ClientPacketID.UPTIME])

    task = TaskUptime(data, message_sender, server_repo)
    await task.execute()

    sent_message = message_sender.send_console_msg.call_args[0][0]

    # Verificar singular (sin 's')
    assert "1 dia," in sent_message or "1 dia " in sent_message
    assert "1 hora," in sent_message or "1 hora " in sent_message
    assert "1 minuto," in sent_message or "1 minuto " in sent_message
    assert "1 segundo" in sent_message
