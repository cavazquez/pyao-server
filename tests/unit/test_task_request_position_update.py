"""Tests para TaskRequestPositionUpdate."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.messaging.message_sender import MessageSender
from src.network.client_connection import ClientConnection
from src.network.packet_id import ClientPacketID, ServerPacketID
from src.repositories.player_repository import PlayerRepository
from src.tasks.player.task_request_position_update import TaskRequestPositionUpdate


@pytest.mark.asyncio
async def test_request_position_update_success() -> None:
    """Verifica que TaskRequestPositionUpdate envíe la posición correcta."""
    # Mock de writer
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    # Mock de PlayerRepository
    player_repo = MagicMock(spec=PlayerRepository)
    player_repo.get_position = AsyncMock(return_value={"x": 75, "y": 80, "map": 1})

    # Crear conexión y message sender
    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)

    # Session data con user_id
    session_data = {"user_id": 123, "username": "testuser"}

    # Construir paquete REQUEST_POSITION_UPDATE (solo PacketID)
    data = bytes([ClientPacketID.REQUEST_POSITION_UPDATE])

    # Crear y ejecutar tarea
    task = TaskRequestPositionUpdate(data, message_sender, player_repo, session_data)
    await task.execute()

    # Verificar que se llamó a get_position
    player_repo.get_position.assert_called_once_with(123)

    # Verificar que se envió POS_UPDATE
    assert writer.write.call_count == 1
    sent_packet = writer.write.call_args[0][0]
    assert sent_packet[0] == ServerPacketID.POS_UPDATE
    assert sent_packet[1] == 75  # x
    assert sent_packet[2] == 80  # y


@pytest.mark.asyncio
async def test_request_position_update_not_logged_in() -> None:
    """Verifica que no se envíe nada si el usuario no está logueado."""
    # Mock de writer
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    # Mock de PlayerRepository
    player_repo = MagicMock(spec=PlayerRepository)

    # Crear conexión y message sender
    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)

    # Session data vacía (no logueado)
    session_data = {}

    # Construir paquete REQUEST_POSITION_UPDATE
    data = bytes([ClientPacketID.REQUEST_POSITION_UPDATE])

    # Crear y ejecutar tarea
    task = TaskRequestPositionUpdate(data, message_sender, player_repo, session_data)
    await task.execute()

    # Verificar que NO se envió ningún paquete
    assert writer.write.call_count == 0


@pytest.mark.asyncio
async def test_request_position_update_no_position_found() -> None:
    """Verifica que se envíe posición por defecto si no se encuentra en Redis."""
    # Mock de writer
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    # Mock de PlayerRepository que devuelve None (no hay posición)
    player_repo = MagicMock(spec=PlayerRepository)
    player_repo.get_position = AsyncMock(return_value=None)

    # Crear conexión y message sender
    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)

    # Session data con user_id
    session_data = {"user_id": 123, "username": "testuser"}

    # Construir paquete REQUEST_POSITION_UPDATE
    data = bytes([ClientPacketID.REQUEST_POSITION_UPDATE])

    # Crear y ejecutar tarea
    task = TaskRequestPositionUpdate(data, message_sender, player_repo, session_data)
    await task.execute()

    # Verificar que se envió POS_UPDATE con posición por defecto (50, 50)
    assert writer.write.call_count == 1
    sent_packet = writer.write.call_args[0][0]
    assert sent_packet[0] == ServerPacketID.POS_UPDATE
    assert sent_packet[1] == 50  # x por defecto
    assert sent_packet[2] == 50  # y por defecto


@pytest.mark.asyncio
async def test_request_position_update_no_player_repo() -> None:
    """Verifica que no se envíe nada si no hay PlayerRepository."""
    # Mock de writer
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    # Crear conexión y message sender
    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)

    # Session data con user_id
    session_data = {"user_id": 123, "username": "testuser"}

    # Construir paquete REQUEST_POSITION_UPDATE
    data = bytes([ClientPacketID.REQUEST_POSITION_UPDATE])

    # Crear y ejecutar tarea sin PlayerRepository
    task = TaskRequestPositionUpdate(data, message_sender, None, session_data)
    await task.execute()

    # Verificar que NO se envió ningún paquete
    assert writer.write.call_count == 0
