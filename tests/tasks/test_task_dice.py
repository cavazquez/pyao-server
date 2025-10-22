"""Tests para TaskDice."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.network.client_connection import ClientConnection
from src.messaging.message_sender import MessageSender
from src.tasks.task_dice import TaskDice


@pytest.mark.asyncio
async def test_task_dice_generates_attributes() -> None:
    """Verifica que TaskDice genera y envía 5 atributos."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()
    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)

    data = bytes([1])  # PacketID ThrowDices
    task = TaskDice(data, message_sender)

    await task.execute()

    # Verificar que se escribió algo
    assert writer.write.called
    written_data = writer.write.call_args[0][0]

    # Verificar formato: PacketID (67) + 5 bytes de atributos
    assert len(written_data) == 6
    assert written_data[0] == 67  # ServerPacketID.DiceRoll

    # Verificar que los atributos están en rango válido (6-18)
    for i in range(1, 6):
        assert 6 <= written_data[i] <= 18

    # Verificar que se llamó drain
    writer.drain.assert_called_once()
