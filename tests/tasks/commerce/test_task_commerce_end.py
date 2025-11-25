"""Tests para TaskCommerceEnd."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.commands.base import CommandResult
from src.commands.commerce_end_command import CommerceEndCommand
from src.messaging.message_sender import MessageSender
from src.network.client_connection import ClientConnection
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
    message_sender.send_commerce_end = AsyncMock()

    # Mock del handler
    commerce_end_handler = MagicMock()
    commerce_end_handler.handle = AsyncMock(return_value=CommandResult.ok())

    # Crear tarea (el paquete solo tiene el PacketID, sin datos adicionales)
    data = bytes([0x11])  # ClientPacketID.COMMERCE_END
    task = TaskCommerceEnd(data, message_sender, commerce_end_handler=commerce_end_handler)

    # Ejecutar tarea
    await task.execute()

    # Verificar que se llamó al handler
    commerce_end_handler.handle.assert_called_once()
    call_args = commerce_end_handler.handle.call_args[0][0]
    assert isinstance(call_args, CommerceEndCommand)


@pytest.mark.asyncio
async def test_commerce_end_multiple_calls():
    """Verifica que se pueda cerrar la ventana múltiples veces."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)
    message_sender.send_commerce_end = AsyncMock()

    # Mock del handler
    commerce_end_handler = MagicMock()
    commerce_end_handler.handle = AsyncMock(return_value=CommandResult.ok())

    data = bytes([0x11])

    # Ejecutar varias veces
    for _ in range(3):
        task = TaskCommerceEnd(data, message_sender, commerce_end_handler=commerce_end_handler)
        await task.execute()

    # Verificar que se llamó 3 veces
    assert commerce_end_handler.handle.call_count == 3
