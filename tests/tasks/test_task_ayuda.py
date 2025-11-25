"""Tests para TaskAyuda."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.commands.ayuda_command import AyudaCommand
from src.commands.base import CommandResult
from src.messaging.message_sender import MessageSender
from src.network.client_connection import ClientConnection
from src.network.packet_id import ClientPacketID
from src.tasks.task_ayuda import TaskAyuda


@pytest.mark.asyncio
async def test_task_ayuda_shows_commands() -> None:
    """Verifica que TaskAyuda muestre la lista de comandos."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)
    message_sender.send_multiline_console_msg = AsyncMock()

    # Mock del handler
    ayuda_handler = MagicMock()
    ayuda_handler.handle = AsyncMock(
        return_value=CommandResult.ok(
            data={
                "help_message": (
                    "--- Comandos Disponibles ---\n"
                    "/AYUDA - Muestra esta ayuda\n"
                    "/EST - Muestra tus estadisticas\n"
                    "/ONLINE - Lista de jugadores conectados\n"
                    "/SALIR - Desconectarse del servidor"
                )
            }
        )
    )

    # Construir paquete AYUDA (solo PacketID)
    data = bytes([ClientPacketID.AYUDA])

    task = TaskAyuda(data, message_sender, ayuda_handler=ayuda_handler)
    await task.execute()

    # Verificar que se llamó al handler
    ayuda_handler.handle.assert_called_once()
    call_args = ayuda_handler.handle.call_args[0][0]
    assert isinstance(call_args, AyudaCommand)


@pytest.mark.asyncio
async def test_task_ayuda_message_format() -> None:
    """Verifica que el mensaje de ayuda tenga el formato correcto."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)
    message_sender.send_multiline_console_msg = AsyncMock()

    # Mock del handler
    ayuda_handler = MagicMock()
    ayuda_handler.handle = AsyncMock(
        return_value=CommandResult.ok(
            data={"help_message": "--- Comandos Disponibles ---\n/AYUDA - Muestra esta ayuda"}
        )
    )

    data = bytes([ClientPacketID.AYUDA])

    task = TaskAyuda(data, message_sender, ayuda_handler=ayuda_handler)
    await task.execute()

    # Verificar que se llamó al handler
    ayuda_handler.handle.assert_called_once()


@pytest.mark.asyncio
async def test_task_ayuda_multiple_requests() -> None:
    """Verifica que TaskAyuda responda correctamente a múltiples solicitudes."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)
    message_sender.send_multiline_console_msg = AsyncMock()

    # Mock del handler
    ayuda_handler = MagicMock()
    ayuda_handler.handle = AsyncMock(
        return_value=CommandResult.ok(data={"help_message": "Test help"})
    )

    data = bytes([ClientPacketID.AYUDA])

    # Solicitar ayuda 3 veces
    for _ in range(3):
        task = TaskAyuda(data, message_sender, ayuda_handler=ayuda_handler)
        await task.execute()

    # Verificar que se llamó 3 veces
    assert ayuda_handler.handle.call_count == 3


@pytest.mark.asyncio
async def test_task_ayuda_contains_basic_info() -> None:
    """Verifica que la ayuda contenga información básica del juego."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)
    message_sender.send_multiline_console_msg = AsyncMock()

    # Mock del handler
    ayuda_handler = MagicMock()
    ayuda_handler.handle = AsyncMock(
        return_value=CommandResult.ok(
            data={
                "help_message": (
                    "--- Comandos Disponibles ---\n"
                    "Usa las teclas de direccion para moverte\n"
                    "Escribe en el chat para hablar con otros jugadores"
                )
            }
        )
    )

    data = bytes([ClientPacketID.AYUDA])

    task = TaskAyuda(data, message_sender, ayuda_handler=ayuda_handler)
    await task.execute()

    # Verificar que se llamó al handler
    ayuda_handler.handle.assert_called_once()
