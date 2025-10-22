"""Tests para TaskRequestStats."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.network.client_connection import ClientConnection
from src.messaging.message_sender import MessageSender
from src.network.packet_id import ClientPacketID
from src.tasks.player.task_request_stats import TaskRequestStats


@pytest.mark.asyncio
async def test_task_request_stats_success() -> None:
    """Verifica que TaskRequestStats muestre las estadísticas del jugador."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    # Mock del player_repo con datos de prueba
    player_repo = MagicMock()
    player_repo.get_stats = AsyncMock(
        return_value={
            "max_hp": 100,
            "min_hp": 80,
            "max_mana": 50,
            "min_mana": 30,
            "max_sta": 100,
            "min_sta": 90,
            "gold": 500,
            "level": 5,
            "elu": 1000,
            "experience": 750,
        }
    )
    player_repo.get_attributes = AsyncMock(
        return_value={
            "strength": 15,
            "agility": 12,
            "intelligence": 10,
            "charisma": 8,
            "constitution": 14,
        }
    )
    player_repo.get_hunger_thirst = AsyncMock(
        return_value={
            "max_water": 100,
            "min_water": 60,
            "max_hunger": 100,
            "min_hunger": 70,
        }
    )

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)
    message_sender.send_multiline_console_msg = AsyncMock()

    # Datos de sesión
    session_data: dict[str, dict[str, int]] = {"user_id": 123}

    # Construir paquete REQUEST_STATS (solo PacketID)
    data = bytes([ClientPacketID.REQUEST_STATS])

    task = TaskRequestStats(data, message_sender, player_repo, session_data)
    await task.execute()

    # Verificar que se llamaron los métodos del repositorio
    player_repo.get_stats.assert_called_once_with(123)
    player_repo.get_attributes.assert_called_once_with(123)
    player_repo.get_hunger_thirst.assert_called_once_with(123)

    # Verificar que se envió el mensaje multilínea
    message_sender.send_multiline_console_msg.assert_called_once()
    sent_message = message_sender.send_multiline_console_msg.call_args[0][0]

    # Verificar que el mensaje contiene las estadísticas esperadas
    assert "--- Estadisticas ---" in sent_message
    assert "Nivel: 5" in sent_message
    assert "Experiencia: 750/1000" in sent_message
    assert "Vida: 80/100" in sent_message
    assert "Mana: 30/50" in sent_message
    assert "Energia: 90/100" in sent_message
    assert "Oro: 500" in sent_message
    assert "Hambre: 70/100" in sent_message
    assert "Sed: 60/100" in sent_message
    assert "--- Atributos ---" in sent_message
    assert "Fuerza: 15" in sent_message
    assert "Agilidad: 12" in sent_message
    assert "Inteligencia: 10" in sent_message
    assert "Carisma: 8" in sent_message
    assert "Constitucion: 14" in sent_message


@pytest.mark.asyncio
async def test_task_request_stats_no_stats() -> None:
    """Verifica que TaskRequestStats maneje el caso cuando no hay estadísticas."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    # Mock del player_repo que retorna None
    player_repo = MagicMock()
    player_repo.get_stats = AsyncMock(return_value=None)

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)
    message_sender.send_console_msg = AsyncMock()

    session_data: dict[str, dict[str, int]] = {"user_id": 123}

    # Construir paquete REQUEST_STATS
    data = bytes([ClientPacketID.REQUEST_STATS])

    task = TaskRequestStats(data, message_sender, player_repo, session_data)
    await task.execute()

    # Verificar que se envió un mensaje de error
    message_sender.send_console_msg.assert_called_once_with(
        "Error: No se pudieron obtener las estadisticas"
    )


@pytest.mark.asyncio
async def test_task_request_stats_no_attributes() -> None:
    """Verifica que TaskRequestStats maneje el caso cuando no hay atributos."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    # Mock del player_repo
    player_repo = MagicMock()
    player_repo.get_stats = AsyncMock(
        return_value={
            "max_hp": 100,
            "min_hp": 80,
            "max_mana": 50,
            "min_mana": 30,
            "max_sta": 100,
            "min_sta": 90,
            "gold": 500,
            "level": 5,
            "elu": 1000,
            "experience": 750,
        }
    )
    player_repo.get_attributes = AsyncMock(return_value=None)

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)
    message_sender.send_console_msg = AsyncMock()

    session_data: dict[str, dict[str, int]] = {"user_id": 123}

    # Construir paquete REQUEST_STATS
    data = bytes([ClientPacketID.REQUEST_STATS])

    task = TaskRequestStats(data, message_sender, player_repo, session_data)
    await task.execute()

    # Verificar que se envió un mensaje de error
    message_sender.send_console_msg.assert_called_once_with(
        "Error: No se pudieron obtener los atributos"
    )


@pytest.mark.asyncio
async def test_task_request_stats_no_hunger_thirst() -> None:
    """Verifica que TaskRequestStats maneje el caso cuando no hay hambre/sed."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    # Mock del player_repo
    player_repo = MagicMock()
    player_repo.get_stats = AsyncMock(
        return_value={
            "max_hp": 100,
            "min_hp": 80,
            "max_mana": 50,
            "min_mana": 30,
            "max_sta": 100,
            "min_sta": 90,
            "gold": 500,
            "level": 5,
            "elu": 1000,
            "experience": 750,
        }
    )
    player_repo.get_attributes = AsyncMock(
        return_value={
            "strength": 15,
            "agility": 12,
            "intelligence": 10,
            "charisma": 8,
            "constitution": 14,
        }
    )
    player_repo.get_hunger_thirst = AsyncMock(return_value=None)

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)
    message_sender.send_console_msg = AsyncMock()

    session_data: dict[str, dict[str, int]] = {"user_id": 123}

    # Construir paquete REQUEST_STATS
    data = bytes([ClientPacketID.REQUEST_STATS])

    task = TaskRequestStats(data, message_sender, player_repo, session_data)
    await task.execute()

    # Verificar que se envió un mensaje de error
    message_sender.send_console_msg.assert_called_once_with(
        "Error: No se pudieron obtener hambre y sed"
    )


@pytest.mark.asyncio
async def test_task_request_stats_no_session() -> None:
    """Verifica que TaskRequestStats falle sin sesión activa."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)

    # Sin session_data
    session_data: dict[str, dict[str, int]] = {}

    # Construir paquete REQUEST_STATS
    data = bytes([ClientPacketID.REQUEST_STATS])

    task = TaskRequestStats(data, message_sender, None, session_data)
    await task.execute()

    # El test pasa si no hay excepciones (solo se loguea warning)


@pytest.mark.asyncio
async def test_task_request_stats_no_repo() -> None:
    """Verifica que TaskRequestStats maneje el caso cuando no hay repositorio."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)
    message_sender.send_console_msg = AsyncMock()

    session_data: dict[str, dict[str, int]] = {"user_id": 123}

    # Construir paquete REQUEST_STATS
    data = bytes([ClientPacketID.REQUEST_STATS])

    task = TaskRequestStats(data, message_sender, None, session_data)
    await task.execute()

    # Verificar que se envió un mensaje de error
    message_sender.send_console_msg.assert_called_once_with("Error: Repositorio no disponible")
