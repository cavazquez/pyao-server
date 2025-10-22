"""Tests para TaskPing."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.network.client_connection import ClientConnection
from src.messaging.message_sender import MessageSender
from src.network.packet_id import ClientPacketID, ServerPacketID
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

    # Construir paquete PING (solo PacketID)
    data = bytes([ClientPacketID.PING])

    task = TaskPing(data, message_sender)
    await task.execute()

    # Verificar que se envió PONG
    connection.send.assert_called_once()
    sent_data = connection.send.call_args[0][0]

    # Verificar que el paquete enviado es PONG
    assert len(sent_data) == 1
    assert sent_data[0] == ServerPacketID.PONG


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

    data = bytes([ClientPacketID.PING])

    # Enviar 3 pings
    for _ in range(3):
        task = TaskPing(data, message_sender)
        await task.execute()

    # Verificar que se enviaron 3 pongs
    assert connection.send.call_count == 3


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

    data = bytes([ClientPacketID.PING])

    task = TaskPing(data, message_sender)
    await task.execute()

    # Obtener el paquete enviado
    sent_data = connection.send.call_args[0][0]

    # Verificar formato: solo debe ser el PacketID PONG
    assert isinstance(sent_data, bytes)
    assert len(sent_data) == 1
    assert sent_data == bytes([ServerPacketID.PONG])
