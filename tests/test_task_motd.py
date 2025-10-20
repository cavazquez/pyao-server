"""Tests para TaskMotd."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.packet_id import ClientPacketID
from src.task_motd import TaskMotd


@pytest.mark.asyncio
async def test_task_motd_with_server_repo() -> None:
    """Verifica que TaskMotd muestre el mensaje desde el repositorio."""
    # Mock del message_sender
    message_sender = MagicMock()
    message_sender.connection.address = "127.0.0.1:12345"
    message_sender.send_multiline_console_msg = AsyncMock()

    # Mock del server_repo
    server_repo = MagicMock()
    server_repo.get_motd = AsyncMock(
        return_value="Bienvenido al servidor!\nMantenimiento programado: Sabado 10pm"
    )

    # Construir paquete REQUEST_MOTD (solo PacketID)
    data = bytes([ClientPacketID.REQUEST_MOTD])

    task = TaskMotd(data, message_sender, server_repo)
    await task.execute()

    # Verificar que se obtuvo el MOTD desde el repositorio
    server_repo.get_motd.assert_called_once()

    # Verificar que se envió el mensaje
    message_sender.send_multiline_console_msg.assert_called_once()
    sent_message = message_sender.send_multiline_console_msg.call_args[0][0]

    assert "Bienvenido al servidor!" in sent_message
    assert "Mantenimiento programado: Sabado 10pm" in sent_message


@pytest.mark.asyncio
async def test_task_motd_without_server_repo() -> None:
    """Verifica que TaskMotd funcione sin repositorio con mensaje por defecto."""
    # Mock del message_sender
    message_sender = MagicMock()
    message_sender.connection.address = "127.0.0.1:12345"
    message_sender.send_multiline_console_msg = AsyncMock()

    # Sin server_repo
    data = bytes([ClientPacketID.REQUEST_MOTD])

    task = TaskMotd(data, message_sender, None)
    await task.execute()

    # Verificar que se envió el mensaje por defecto
    message_sender.send_multiline_console_msg.assert_called_once()
    sent_message = message_sender.send_multiline_console_msg.call_args[0][0]

    assert "Bienvenido a Argentum Online!" in sent_message
    assert "Servidor en desarrollo" in sent_message


@pytest.mark.asyncio
async def test_task_motd_multiline_message() -> None:
    """Verifica que TaskMotd maneje correctamente mensajes multilínea."""
    # Mock del message_sender
    message_sender = MagicMock()
    message_sender.connection.address = "127.0.0.1:12345"
    message_sender.send_multiline_console_msg = AsyncMock()

    # Mock del server_repo con mensaje multilínea
    server_repo = MagicMock()
    server_repo.get_motd = AsyncMock(return_value="Linea 1\nLinea 2\nLinea 3\nLinea 4")

    data = bytes([ClientPacketID.REQUEST_MOTD])

    task = TaskMotd(data, message_sender, server_repo)
    await task.execute()

    sent_message = message_sender.send_multiline_console_msg.call_args[0][0]

    # Verificar que tiene saltos de línea
    assert "\n" in sent_message
    assert "Linea 1" in sent_message
    assert "Linea 4" in sent_message


@pytest.mark.asyncio
async def test_task_motd_multiple_requests() -> None:
    """Verifica que TaskMotd responda correctamente a múltiples solicitudes."""
    # Mock del message_sender
    message_sender = MagicMock()
    message_sender.connection.address = "127.0.0.1:12345"
    message_sender.send_multiline_console_msg = AsyncMock()

    server_repo = MagicMock()
    server_repo.get_motd = AsyncMock(return_value="Test MOTD")

    data = bytes([ClientPacketID.REQUEST_MOTD])

    # Solicitar MOTD 3 veces
    for _ in range(3):
        task = TaskMotd(data, message_sender, server_repo)
        await task.execute()

    # Verificar que se envió 3 veces
    assert message_sender.send_multiline_console_msg.call_count == 3
    assert server_repo.get_motd.call_count == 3
