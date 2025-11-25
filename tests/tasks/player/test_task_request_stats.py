"""Tests para TaskRequestStats."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.commands.base import CommandResult
from src.commands.request_stats_command import RequestStatsCommand
from src.messaging.message_sender import MessageSender
from src.network.client_connection import ClientConnection
from src.network.packet_id import ClientPacketID
from src.tasks.player.task_request_stats import TaskRequestStats


@pytest.mark.asyncio
async def test_task_request_stats_success() -> None:
    """Verifica que TaskRequestStats muestre las estadísticas del jugador."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)
    message_sender.send_multiline_console_msg = AsyncMock()

    # Mock del handler
    request_stats_handler = MagicMock()
    request_stats_handler.handle = AsyncMock(
        return_value=CommandResult.ok(
            data={
                "user_id": 123,
                "stats": {
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
                },
                "attributes": {
                    "strength": 15,
                    "agility": 12,
                    "intelligence": 10,
                    "charisma": 8,
                    "constitution": 14,
                },
                "hunger_thirst": {
                    "max_water": 100,
                    "min_water": 60,
                    "max_hunger": 100,
                    "min_hunger": 70,
                },
            }
        )
    )

    # Datos de sesión
    session_data: dict[str, dict[str, int]] = {"user_id": 123}

    # Construir paquete REQUEST_STATS (solo PacketID)
    data = bytes([ClientPacketID.REQUEST_STATS])

    task = TaskRequestStats(
        data, message_sender, request_stats_handler=request_stats_handler, session_data=session_data
    )
    await task.execute()

    # Verificar que se llamó al handler
    request_stats_handler.handle.assert_called_once()
    call_args = request_stats_handler.handle.call_args[0][0]
    assert isinstance(call_args, RequestStatsCommand)
    assert call_args.user_id == 123


@pytest.mark.asyncio
async def test_task_request_stats_no_stats() -> None:
    """Verifica que TaskRequestStats maneje el caso cuando no hay estadísticas."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)
    message_sender.send_console_msg = AsyncMock()

    # Mock del handler que retorna error
    request_stats_handler = MagicMock()
    request_stats_handler.handle = AsyncMock(
        return_value=CommandResult.error("No se pudieron obtener las estadísticas")
    )

    session_data: dict[str, dict[str, int]] = {"user_id": 123}

    # Construir paquete REQUEST_STATS
    data = bytes([ClientPacketID.REQUEST_STATS])

    task = TaskRequestStats(
        data, message_sender, request_stats_handler=request_stats_handler, session_data=session_data
    )
    await task.execute()

    # Verificar que se llamó al handler
    request_stats_handler.handle.assert_called_once()


@pytest.mark.asyncio
async def test_task_request_stats_no_attributes() -> None:
    """Verifica que TaskRequestStats maneje el caso cuando no hay atributos."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)

    # Mock del handler que retorna error
    request_stats_handler = MagicMock()
    request_stats_handler.handle = AsyncMock(
        return_value=CommandResult.error("No se pudieron obtener los atributos")
    )

    session_data: dict[str, dict[str, int]] = {"user_id": 123}

    # Construir paquete REQUEST_STATS
    data = bytes([ClientPacketID.REQUEST_STATS])

    task = TaskRequestStats(
        data, message_sender, request_stats_handler=request_stats_handler, session_data=session_data
    )
    await task.execute()

    # Verificar que se llamó al handler
    request_stats_handler.handle.assert_called_once()


@pytest.mark.asyncio
async def test_task_request_stats_no_hunger_thirst() -> None:
    """Verifica que TaskRequestStats maneje el caso cuando no hay hambre/sed."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)

    # Mock del handler que retorna error
    request_stats_handler = MagicMock()
    request_stats_handler.handle = AsyncMock(
        return_value=CommandResult.error("No se pudieron obtener hambre y sed")
    )

    session_data: dict[str, dict[str, int]] = {"user_id": 123}

    # Construir paquete REQUEST_STATS
    data = bytes([ClientPacketID.REQUEST_STATS])

    task = TaskRequestStats(
        data, message_sender, request_stats_handler=request_stats_handler, session_data=session_data
    )
    await task.execute()

    # Verificar que se llamó al handler
    request_stats_handler.handle.assert_called_once()


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

    task = TaskRequestStats(
        data, message_sender, request_stats_handler=None, session_data=session_data
    )
    await task.execute()

    # El test pasa si no hay excepciones (solo se loguea warning)


@pytest.mark.asyncio
async def test_task_request_stats_no_handler() -> None:
    """Verifica que TaskRequestStats maneje el caso cuando no hay handler."""
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

    task = TaskRequestStats(
        data, message_sender, request_stats_handler=None, session_data=session_data
    )
    await task.execute()

    # Verificar que se envió un mensaje de error
    message_sender.send_console_msg.assert_called_once_with("Error: Repositorio no disponible")
