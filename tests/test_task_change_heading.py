"""Tests para TaskChangeHeading."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.client_connection import ClientConnection
from src.messaging.message_sender import MessageSender
from src.packet_id import ClientPacketID
from src.player_repository import PlayerRepository
from src.tasks.player.task_change_heading import TaskChangeHeading


@pytest.mark.asyncio
async def test_task_change_heading_success() -> None:
    """Verifica que TaskChangeHeading guarde la dirección correctamente."""
    # Mock del writer
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    # Mock del player_repo
    player_repo = MagicMock(spec=PlayerRepository)
    player_repo.set_heading = AsyncMock()

    # Crear conexión y message sender
    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)

    # Datos de sesión con user_id
    session_data: dict[str, dict[str, int]] = {"user_id": 123}

    # Construir paquete CHANGE_HEADING con dirección Este (2)
    heading = 2
    data = bytes([ClientPacketID.CHANGE_HEADING, heading])

    # Crear y ejecutar tarea
    task = TaskChangeHeading(data, message_sender, player_repo, None, None, session_data)
    await task.execute()

    # Verificar que se llamó a set_heading con los parámetros correctos
    player_repo.set_heading.assert_called_once_with(123, heading)


@pytest.mark.asyncio
async def test_task_change_heading_all_directions() -> None:
    """Verifica que TaskChangeHeading funcione con todas las direcciones."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    player_repo = MagicMock(spec=PlayerRepository)
    player_repo.set_heading = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)

    session_data: dict[str, dict[str, int]] = {"user_id": 456}

    # Probar todas las direcciones: 1=Norte, 2=Este, 3=Sur, 4=Oeste
    for heading in [1, 2, 3, 4]:
        data = bytes([ClientPacketID.CHANGE_HEADING, heading])
        task = TaskChangeHeading(data, message_sender, player_repo, None, None, session_data)
        await task.execute()

    # Verificar que se llamó 4 veces
    assert player_repo.set_heading.call_count == 4


@pytest.mark.asyncio
async def test_task_change_heading_invalid_direction() -> None:
    """Verifica que TaskChangeHeading rechace direcciones inválidas."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    player_repo = MagicMock(spec=PlayerRepository)
    player_repo.set_heading = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)

    session_data: dict[str, dict[str, int]] = {"user_id": 789}

    # Probar dirección inválida (5)
    data = bytes([ClientPacketID.CHANGE_HEADING, 5])
    task = TaskChangeHeading(data, message_sender, player_repo, None, None, session_data)
    await task.execute()

    # Verificar que NO se llamó a set_heading
    player_repo.set_heading.assert_not_called()


@pytest.mark.asyncio
async def test_task_change_heading_no_session() -> None:
    """Verifica que TaskChangeHeading falle sin user_id en sesión."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    player_repo = MagicMock(spec=PlayerRepository)
    player_repo.set_heading = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)

    # Sin session_data
    session_data: dict[str, dict[str, int]] = {}

    data = bytes([ClientPacketID.CHANGE_HEADING, 1])
    task = TaskChangeHeading(data, message_sender, player_repo, None, None, session_data)
    await task.execute()

    # Verificar que NO se llamó a set_heading
    player_repo.set_heading.assert_not_called()


@pytest.mark.asyncio
async def test_task_change_heading_no_player_repo() -> None:
    """Verifica que TaskChangeHeading falle sin PlayerRepository."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)

    session_data: dict[str, dict[str, int]] = {"user_id": 999}

    data = bytes([ClientPacketID.CHANGE_HEADING, 1])
    # Sin player_repo
    task = TaskChangeHeading(data, message_sender, None, None, None, session_data)
    await task.execute()

    # No debería haber errores, solo un log de error


@pytest.mark.asyncio
async def test_task_change_heading_invalid_packet() -> None:
    """Verifica que TaskChangeHeading rechace paquetes inválidos."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    player_repo = MagicMock(spec=PlayerRepository)
    player_repo.set_heading = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)

    session_data: dict[str, dict[str, int]] = {"user_id": 111}

    # Paquete demasiado corto
    data = bytes([ClientPacketID.CHANGE_HEADING])
    task = TaskChangeHeading(data, message_sender, player_repo, None, None, session_data)
    await task.execute()

    # Verificar que NO se llamó a set_heading
    player_repo.set_heading.assert_not_called()
