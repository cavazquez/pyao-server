"""Tests para TaskAyuda."""

from unittest.mock import AsyncMock, MagicMock

import pytest

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

    # Construir paquete AYUDA (solo PacketID)
    data = bytes([ClientPacketID.AYUDA])

    task = TaskAyuda(data, message_sender)
    await task.execute()

    # Verificar que se envió el mensaje de ayuda
    message_sender.send_multiline_console_msg.assert_called_once()
    sent_message = message_sender.send_multiline_console_msg.call_args[0][0]

    # Verificar que el mensaje contiene información de comandos
    assert "Comandos Disponibles" in sent_message
    assert "/AYUDA" in sent_message
    assert "/EST" in sent_message
    assert "/ONLINE" in sent_message
    assert "/SALIR" in sent_message


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

    data = bytes([ClientPacketID.AYUDA])

    task = TaskAyuda(data, message_sender)
    await task.execute()

    sent_message = message_sender.send_multiline_console_msg.call_args[0][0]

    # Verificar que tiene saltos de línea (es multilínea)
    assert "\n" in sent_message

    # Verificar que tiene secciones
    lines = sent_message.split("\n")
    assert len(lines) > 5  # Debe tener varias líneas


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

    data = bytes([ClientPacketID.AYUDA])

    # Solicitar ayuda 3 veces
    for _ in range(3):
        task = TaskAyuda(data, message_sender)
        await task.execute()

    # Verificar que se envió 3 veces
    assert message_sender.send_multiline_console_msg.call_count == 3


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

    data = bytes([ClientPacketID.AYUDA])

    task = TaskAyuda(data, message_sender)
    await task.execute()

    sent_message = message_sender.send_multiline_console_msg.call_args[0][0]

    # Verificar que contiene información útil
    assert "---" in sent_message  # Tiene separadores
    # Debe mencionar algo sobre movimiento o chat
    message_lower = sent_message.lower()
    assert "mover" in message_lower or "chat" in message_lower or "hablar" in message_lower
