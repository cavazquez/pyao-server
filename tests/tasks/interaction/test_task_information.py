"""Tests para TaskInformation."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.commands.base import CommandResult
from src.commands.information_command import InformationCommand
from src.messaging.message_sender import MessageSender
from src.network.client_connection import ClientConnection
from src.network.packet_id import ClientPacketID
from src.tasks.interaction.task_information import TaskInformation


@pytest.mark.asyncio
async def test_task_information_complete() -> None:
    """Verifica que TaskInformation muestre toda la información del servidor."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)
    message_sender.send_multiline_console_msg = AsyncMock()

    # Mock del handler
    information_handler = MagicMock()
    information_handler.handle = AsyncMock(
        return_value=CommandResult.ok(
            data={
                "message": (
                    "--- Informacion del Servidor ---\n"
                    "Nombre: Argentum Online\n"
                    "Version: PyAO 0.1.0\n"
                    "Jugadores conectados: 3\n"
                    "Uptime: 2h 0m\n"
                    "Usa /AYUDA para ver comandos"
                )
            }
        )
    )

    # Construir paquete INFORMATION (solo PacketID)
    data = bytes([ClientPacketID.INFORMATION])

    task = TaskInformation(data, message_sender, information_handler=information_handler)
    await task.execute()

    # Verificar que se llamó al handler
    information_handler.handle.assert_called_once()
    call_args = information_handler.handle.call_args[0][0]
    assert isinstance(call_args, InformationCommand)


@pytest.mark.asyncio
async def test_task_information_uptime_format() -> None:
    """Verifica que TaskInformation formatee correctamente el uptime."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)
    message_sender.send_multiline_console_msg = AsyncMock()

    # Mock del handler
    information_handler = MagicMock()
    information_handler.handle = AsyncMock(
        return_value=CommandResult.ok(
            data={"message": "--- Informacion del Servidor ---\nUptime: 2d 5h 30m"}
        )
    )

    data = bytes([ClientPacketID.INFORMATION])

    task = TaskInformation(data, message_sender, information_handler=information_handler)
    await task.execute()

    # Verificar que se llamó al handler
    information_handler.handle.assert_called_once()


@pytest.mark.asyncio
async def test_task_information_no_players() -> None:
    """Verifica que TaskInformation muestre 0 jugadores cuando no hay nadie conectado."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)
    message_sender.send_multiline_console_msg = AsyncMock()

    # Mock del handler
    information_handler = MagicMock()
    information_handler.handle = AsyncMock(
        return_value=CommandResult.ok(
            data={"message": "--- Informacion del Servidor ---\nJugadores conectados: 0"}
        )
    )

    data = bytes([ClientPacketID.INFORMATION])

    task = TaskInformation(data, message_sender, information_handler=information_handler)
    await task.execute()

    # Verificar que se llamó al handler
    information_handler.handle.assert_called_once()


@pytest.mark.asyncio
async def test_task_information_without_map_manager() -> None:
    """Verifica que TaskInformation funcione sin MapManager."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)
    message_sender.send_multiline_console_msg = AsyncMock()

    # Mock del handler
    information_handler = MagicMock()
    information_handler.handle = AsyncMock(
        return_value=CommandResult.ok(
            data={"message": "--- Informacion del Servidor ---\nJugadores conectados: N/A"}
        )
    )

    data = bytes([ClientPacketID.INFORMATION])

    task = TaskInformation(data, message_sender, information_handler=information_handler)
    await task.execute()

    # Verificar que se llamó al handler
    information_handler.handle.assert_called_once()


@pytest.mark.asyncio
async def test_task_information_without_server_repo() -> None:
    """Verifica que TaskInformation funcione sin ServerRepository."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)
    message_sender.send_multiline_console_msg = AsyncMock()

    # Mock del handler
    information_handler = MagicMock()
    information_handler.handle = AsyncMock(
        return_value=CommandResult.ok(
            data={
                "message": (
                    "--- Informacion del Servidor ---\n"
                    "Nombre: Argentum Online\n"
                    "Jugadores conectados: 1"
                )
            }
        )
    )

    data = bytes([ClientPacketID.INFORMATION])

    task = TaskInformation(data, message_sender, information_handler=information_handler)
    await task.execute()

    # Verificar que se llamó al handler
    information_handler.handle.assert_called_once()


@pytest.mark.asyncio
async def test_task_information_uptime_hours_only() -> None:
    """Verifica formato de uptime cuando solo hay horas."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)
    message_sender.send_multiline_console_msg = AsyncMock()

    # Mock del handler
    information_handler = MagicMock()
    information_handler.handle = AsyncMock(
        return_value=CommandResult.ok(
            data={"message": "--- Informacion del Servidor ---\nUptime: 3h 45m"}
        )
    )

    data = bytes([ClientPacketID.INFORMATION])

    task = TaskInformation(data, message_sender, information_handler=information_handler)
    await task.execute()

    # Verificar que se llamó al handler
    information_handler.handle.assert_called_once()
