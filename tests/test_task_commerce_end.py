"""Tests para TaskCommerceEnd."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.client_connection import ClientConnection
from src.messaging.message_sender import MessageSender
from src.packet_id import ServerPacketID
from src.tasks.commerce.task_commerce_end import TaskCommerceEnd


@pytest.mark.asyncio
async def test_commerce_end_success():
    """Verifica que TaskCommerceEnd envíe el paquete COMMERCE_END."""
    # Mock del writer
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    # Crear conexión y message sender
    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)

    # Crear tarea (el paquete solo tiene el PacketID, sin datos adicionales)
    data = bytes([0x11])  # ClientPacketID.COMMERCE_END
    task = TaskCommerceEnd(data, message_sender)

    # Ejecutar tarea
    await task.execute()

    # Verificar que se envió el paquete COMMERCE_END
    assert writer.write.call_count == 1
    sent_data = writer.write.call_args[0][0]
    assert sent_data[0] == ServerPacketID.COMMERCE_END
    assert len(sent_data) == 1  # Solo el PacketID


@pytest.mark.asyncio
async def test_commerce_end_multiple_calls():
    """Verifica que se pueda cerrar la ventana múltiples veces."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)

    data = bytes([0x11])

    # Ejecutar varias veces
    for _ in range(3):
        task = TaskCommerceEnd(data, message_sender)
        await task.execute()

    # Verificar que se envió 3 veces
    assert writer.write.call_count == 3
    for call in writer.write.call_args_list:
        sent_data = call[0][0]
        assert sent_data[0] == ServerPacketID.COMMERCE_END
