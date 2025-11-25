"""Tests para TaskMotd."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.commands.base import CommandResult
from src.commands.motd_command import MotdCommand
from src.network.packet_id import ClientPacketID
from src.tasks.task_motd import TaskMotd


@pytest.mark.asyncio
async def test_task_motd_with_server_repo() -> None:
    """Verifica que TaskMotd muestre el mensaje desde el repositorio."""
    # Mock del message_sender
    message_sender = MagicMock()
    message_sender.connection.address = "127.0.0.1:12345"
    message_sender.send_multiline_console_msg = AsyncMock()

    # Mock del handler
    motd_handler = MagicMock()
    motd_handler.handle = AsyncMock(
        return_value=CommandResult.ok(
            data={"motd": "Bienvenido al servidor!\nMantenimiento programado: Sabado 10pm"}
        )
    )

    # Construir paquete REQUEST_MOTD (solo PacketID)
    data = bytes([ClientPacketID.REQUEST_MOTD])

    task = TaskMotd(data, message_sender, motd_handler=motd_handler)
    await task.execute()

    # Verificar que se llamó al handler
    motd_handler.handle.assert_called_once()
    call_args = motd_handler.handle.call_args[0][0]
    assert isinstance(call_args, MotdCommand)


@pytest.mark.asyncio
async def test_task_motd_without_server_repo() -> None:
    """Verifica que TaskMotd funcione sin repositorio con mensaje por defecto."""
    # Mock del message_sender
    message_sender = MagicMock()
    message_sender.connection.address = "127.0.0.1:12345"
    message_sender.send_multiline_console_msg = AsyncMock()

    # Mock del handler
    motd_handler = MagicMock()
    motd_handler.handle = AsyncMock(
        return_value=CommandResult.ok(
            data={"motd": "» Bienvenido a Argentum Online! «\n• Servidor en desarrollo."}
        )
    )

    # Sin server_repo
    data = bytes([ClientPacketID.REQUEST_MOTD])

    task = TaskMotd(data, message_sender, motd_handler=motd_handler)
    await task.execute()

    # Verificar que se llamó al handler
    motd_handler.handle.assert_called_once()


@pytest.mark.asyncio
async def test_task_motd_multiline_message() -> None:
    """Verifica que TaskMotd maneje correctamente mensajes multilínea."""
    # Mock del message_sender
    message_sender = MagicMock()
    message_sender.connection.address = "127.0.0.1:12345"
    message_sender.send_multiline_console_msg = AsyncMock()

    # Mock del handler
    motd_handler = MagicMock()
    motd_handler.handle = AsyncMock(
        return_value=CommandResult.ok(data={"motd": "Linea 1\nLinea 2\nLinea 3\nLinea 4"})
    )

    data = bytes([ClientPacketID.REQUEST_MOTD])

    task = TaskMotd(data, message_sender, motd_handler=motd_handler)
    await task.execute()

    # Verificar que se llamó al handler
    motd_handler.handle.assert_called_once()


@pytest.mark.asyncio
async def test_task_motd_multiple_requests() -> None:
    """Verifica que TaskMotd responda correctamente a múltiples solicitudes."""
    # Mock del message_sender
    message_sender = MagicMock()
    message_sender.connection.address = "127.0.0.1:12345"
    message_sender.send_multiline_console_msg = AsyncMock()

    # Mock del handler
    motd_handler = MagicMock()
    motd_handler.handle = AsyncMock(return_value=CommandResult.ok(data={"motd": "Test MOTD"}))

    data = bytes([ClientPacketID.REQUEST_MOTD])

    # Solicitar MOTD 3 veces
    for _ in range(3):
        task = TaskMotd(data, message_sender, motd_handler=motd_handler)
        await task.execute()

    # Verificar que se llamó 3 veces
    assert motd_handler.handle.call_count == 3
