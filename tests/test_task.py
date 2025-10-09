"""Tests para el sistema de tareas."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.client_connection import ClientConnection
from src.task import TaskDice, TaskNull


@pytest.mark.asyncio
async def test_task_null_logs_unknown_packet() -> None:
    """Verifica que TaskNull loguea información del paquete desconocido."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    connection = ClientConnection(writer)

    data = bytes([99, 1, 2, 3, 4, 5])  # PacketID 99 (desconocido)
    task = TaskNull(data, connection)

    # No debería lanzar excepción
    await task.execute()

    # Verificar que se obtuvo la info del cliente
    writer.get_extra_info.assert_called_once_with("peername")


@pytest.mark.asyncio
async def test_task_dice_generates_attributes() -> None:
    """Verifica que TaskDice genera y envía 5 atributos."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()
    connection = ClientConnection(writer)

    data = bytes([1])  # PacketID ThrowDices
    task = TaskDice(data, connection)

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
