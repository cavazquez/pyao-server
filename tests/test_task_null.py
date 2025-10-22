"""Tests para TaskNull."""

from unittest.mock import MagicMock

import pytest

from src.network.client_connection import ClientConnection
from src.messaging.message_sender import MessageSender
from src.tasks.task_null import TaskNull


@pytest.mark.asyncio
async def test_task_null_logs_unknown_packet() -> None:
    """Verifica que TaskNull loguea información del paquete desconocido."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)

    data = bytes([99, 1, 2, 3, 4, 5])  # PacketID 99 (desconocido)
    task = TaskNull(data, message_sender)

    # No debería lanzar excepción
    await task.execute()

    # Verificar que se obtuvo la info del cliente
    writer.get_extra_info.assert_called_once_with("peername")
