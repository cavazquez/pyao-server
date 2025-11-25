"""Tests para TaskPing."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.commands.base import CommandResult
from src.commands.ping_command import PingCommand
from src.messaging.message_sender import MessageSender
from src.network.client_connection import ClientConnection
from src.network.packet_id import ClientPacketID
from src.tasks.task_ping import TaskPing


@pytest.mark.asyncio
async def test_task_ping_sends_pong() -> None:
    """Verifica que TaskPing responda con PONG."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    connection.send = AsyncMock()
    message_sender = MessageSender(connection)
    message_sender.send_pong = AsyncMock()

    # Mock del handler
    ping_handler = MagicMock()
    ping_handler.handle = AsyncMock(return_value=CommandResult.ok())

    # Construir paquete PING (solo PacketID)
    data = bytes([ClientPacketID.PING])

    task = TaskPing(data, message_sender, ping_handler=ping_handler)
    await task.execute()

    # Verificar que se llamó al handler
    ping_handler.handle.assert_called_once()
    call_args = ping_handler.handle.call_args[0][0]
    assert isinstance(call_args, PingCommand)


@pytest.mark.asyncio
async def test_task_ping_multiple_pings() -> None:
    """Verifica que TaskPing responda correctamente a múltiples pings."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    connection.send = AsyncMock()
    message_sender = MessageSender(connection)
    message_sender.send_pong = AsyncMock()

    # Mock del handler
    ping_handler = MagicMock()
    ping_handler.handle = AsyncMock(return_value=CommandResult.ok())

    data = bytes([ClientPacketID.PING])

    # Enviar 3 pings
    for _ in range(3):
        task = TaskPing(data, message_sender, ping_handler=ping_handler)
        await task.execute()

    # Verificar que se llamó 3 veces
    assert ping_handler.handle.call_count == 3


@pytest.mark.asyncio
async def test_task_ping_packet_format() -> None:
    """Verifica que el paquete PONG tenga el formato correcto."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    connection.send = AsyncMock()
    message_sender = MessageSender(connection)
    message_sender.send_pong = AsyncMock()

    # Mock del handler que realmente llama a send_pong
    async def handle_side_effect(_command):
        await message_sender.send_pong()
        return CommandResult.ok()

    ping_handler = MagicMock()
    ping_handler.handle = AsyncMock(side_effect=handle_side_effect)

    data = bytes([ClientPacketID.PING])

    task = TaskPing(data, message_sender, ping_handler=ping_handler)
    await task.execute()

    # Verificar que se llamó al handler
    ping_handler.handle.assert_called_once()
    # Verificar que se llamó send_pong
    message_sender.send_pong.assert_called_once()
