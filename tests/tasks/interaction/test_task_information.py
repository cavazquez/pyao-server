"""Tests para TaskInformation."""

import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.network.client_connection import ClientConnection
from src.messaging.message_sender import MessageSender
from src.network.packet_id import ClientPacketID
from src.tasks.interaction.task_information import TaskInformation


@pytest.mark.asyncio
async def test_task_information_complete() -> None:
    """Verifica que TaskInformation muestre toda la información del servidor."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)
    message_sender.send_multiline_console_msg = AsyncMock()

    # Mock del server_repo
    server_repo = MagicMock()
    current_time = int(time.time())
    server_repo.get_uptime_start = AsyncMock(return_value=current_time - 7200)  # 2 horas

    # Mock del map_manager
    map_manager = MagicMock()
    map_manager.get_all_connected_players = MagicMock(
        return_value=["Player1", "Player2", "Player3"]
    )

    # Construir paquete INFORMATION (solo PacketID)
    data = bytes([ClientPacketID.INFORMATION])

    task = TaskInformation(data, message_sender, server_repo, map_manager)
    await task.execute()

    # Verificar que se envió el mensaje
    message_sender.send_multiline_console_msg.assert_called_once()
    sent_message = message_sender.send_multiline_console_msg.call_args[0][0]

    # Verificar contenido
    assert "Informacion del Servidor" in sent_message
    assert "Argentum Online" in sent_message
    assert "PyAO" in sent_message
    assert "Jugadores conectados: 3" in sent_message
    assert "Uptime:" in sent_message
    assert "/AYUDA" in sent_message


@pytest.mark.asyncio
async def test_task_information_uptime_format() -> None:
    """Verifica que TaskInformation formatee correctamente el uptime."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)
    message_sender.send_multiline_console_msg = AsyncMock()

    # Mock del server_repo con 2 días, 5 horas, 30 minutos
    server_repo = MagicMock()
    current_time = int(time.time())
    uptime_seconds = (2 * 86400) + (5 * 3600) + (30 * 60)
    server_repo.get_uptime_start = AsyncMock(return_value=current_time - uptime_seconds)

    map_manager = MagicMock()
    map_manager.get_all_connected_players = MagicMock(return_value=[])

    data = bytes([ClientPacketID.INFORMATION])

    task = TaskInformation(data, message_sender, server_repo, map_manager)
    await task.execute()

    sent_message = message_sender.send_multiline_console_msg.call_args[0][0]

    # Verificar formato resumido del uptime
    assert "2d 5h 30m" in sent_message


@pytest.mark.asyncio
async def test_task_information_no_players() -> None:
    """Verifica que TaskInformation muestre 0 jugadores cuando no hay nadie conectado."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)
    message_sender.send_multiline_console_msg = AsyncMock()

    server_repo = MagicMock()
    server_repo.get_uptime_start = AsyncMock(return_value=int(time.time()) - 3600)

    map_manager = MagicMock()
    map_manager.get_all_connected_players = MagicMock(return_value=[])

    data = bytes([ClientPacketID.INFORMATION])

    task = TaskInformation(data, message_sender, server_repo, map_manager)
    await task.execute()

    sent_message = message_sender.send_multiline_console_msg.call_args[0][0]

    assert "Jugadores conectados: 0" in sent_message


@pytest.mark.asyncio
async def test_task_information_without_map_manager() -> None:
    """Verifica que TaskInformation funcione sin MapManager."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)
    message_sender.send_multiline_console_msg = AsyncMock()

    server_repo = MagicMock()
    server_repo.get_uptime_start = AsyncMock(return_value=int(time.time()) - 3600)

    data = bytes([ClientPacketID.INFORMATION])

    task = TaskInformation(data, message_sender, server_repo, None)
    await task.execute()

    sent_message = message_sender.send_multiline_console_msg.call_args[0][0]

    assert "Jugadores conectados: N/A" in sent_message


@pytest.mark.asyncio
async def test_task_information_without_server_repo() -> None:
    """Verifica que TaskInformation funcione sin ServerRepository."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)
    message_sender.send_multiline_console_msg = AsyncMock()

    map_manager = MagicMock()
    map_manager.get_all_connected_players = MagicMock(return_value=["Player1"])

    data = bytes([ClientPacketID.INFORMATION])

    task = TaskInformation(data, message_sender, None, map_manager)
    await task.execute()

    sent_message = message_sender.send_multiline_console_msg.call_args[0][0]

    # Debe mostrar info básica sin uptime
    assert "Argentum Online" in sent_message
    assert "Jugadores conectados: 1" in sent_message
    assert "Uptime:" not in sent_message


@pytest.mark.asyncio
async def test_task_information_uptime_hours_only() -> None:
    """Verifica formato de uptime cuando solo hay horas."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)
    message_sender.send_multiline_console_msg = AsyncMock()

    # Mock del server_repo con 3 horas, 45 minutos
    server_repo = MagicMock()
    current_time = int(time.time())
    uptime_seconds = (3 * 3600) + (45 * 60)
    server_repo.get_uptime_start = AsyncMock(return_value=current_time - uptime_seconds)

    map_manager = MagicMock()
    map_manager.get_all_connected_players = MagicMock(return_value=[])

    data = bytes([ClientPacketID.INFORMATION])

    task = TaskInformation(data, message_sender, server_repo, map_manager)
    await task.execute()

    sent_message = message_sender.send_multiline_console_msg.call_args[0][0]

    assert "3h 45m" in sent_message
    # Verificar que no tenga formato de días (ej: "2d")
    assert "Uptime: 3h 45m" in sent_message
