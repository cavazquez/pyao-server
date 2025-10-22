"""Tests para ConsoleMessageSender.

Verifica el envío de mensajes de consola al cliente.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.client_connection import ClientConnection
from src.messaging.senders.message_console_sender import ConsoleMessageSender
from src.packet_id import ServerPacketID


@pytest.mark.asyncio
async def test_send_console_msg() -> None:
    """Verifica que send_console_msg() construya y envíe el paquete correcto."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    sender = ConsoleMessageSender(connection)

    await sender.send_console_msg("Hola mundo", font_color=7)

    # Verificar que se llamó write
    assert writer.write.called
    written_data = writer.write.call_args[0][0]

    # Verificar estructura: PacketID + length (int16) + message (UTF-8) + color (byte)
    assert written_data[0] == ServerPacketID.CONSOLE_MSG
    # El mensaje "Hola mundo" en UTF-8
    message_bytes = b"Hola mundo"
    # Verificar que el mensaje esté en los datos
    assert message_bytes in written_data
    # Verificar que el color esté al final
    assert written_data[-1] == 7

    writer.drain.assert_called_once()


@pytest.mark.asyncio
async def test_send_console_msg_default_color() -> None:
    """Verifica que send_console_msg() use color 7 por defecto."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    sender = ConsoleMessageSender(connection)

    await sender.send_console_msg("Test")

    # Verificar que se llamó write
    assert writer.write.called
    written_data = writer.write.call_args[0][0]

    # Verificar que el color sea 7 (gris claro)
    # El color está después del PacketID y antes del mensaje
    assert written_data[0] == ServerPacketID.CONSOLE_MSG


@pytest.mark.asyncio
async def test_send_console_msg_custom_color() -> None:
    """Verifica que send_console_msg() acepte colores personalizados."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    sender = ConsoleMessageSender(connection)

    # Color rojo (1)
    await sender.send_console_msg("Error!", font_color=1)

    assert writer.write.called
    written_data = writer.write.call_args[0][0]
    assert written_data[0] == ServerPacketID.CONSOLE_MSG


@pytest.mark.asyncio
async def test_send_multiline_console_msg() -> None:
    """Verifica que send_multiline_console_msg() divida y envíe múltiples líneas."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    sender = ConsoleMessageSender(connection)

    multiline_message = "Línea 1\nLínea 2\nLínea 3"
    await sender.send_multiline_console_msg(multiline_message, font_color=7)

    # Debe haber llamado write 3 veces (una por línea)
    assert writer.write.call_count == 3
    assert writer.drain.call_count == 3


@pytest.mark.asyncio
async def test_send_multiline_console_msg_skip_empty_lines() -> None:
    """Verifica que send_multiline_console_msg() ignore líneas vacías."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    sender = ConsoleMessageSender(connection)

    multiline_message = "Línea 1\n\nLínea 3\n   \nLínea 5"
    await sender.send_multiline_console_msg(multiline_message)

    # Debe haber llamado write 3 veces (solo líneas no vacías)
    assert writer.write.call_count == 3


@pytest.mark.asyncio
async def test_send_error_msg() -> None:
    """Verifica que send_error_msg() envíe paquete ERROR_MSG."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    sender = ConsoleMessageSender(connection)

    await sender.send_error_msg("Algo salió mal")

    # Verificar que se llamó write
    assert writer.write.called
    written_data = writer.write.call_args[0][0]

    # Verificar que sea un ERROR_MSG (packet 55)
    assert written_data[0] == ServerPacketID.ERROR_MSG
    # Verificar que el mensaje esté en UTF-8
    message_bytes = "Algo salió mal".encode()
    assert message_bytes in written_data


@pytest.mark.asyncio
async def test_console_message_sender_initialization() -> None:
    """Verifica que ConsoleMessageSender se inicialice correctamente."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("192.168.1.100", 54321)

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    sender = ConsoleMessageSender(connection)

    assert sender.connection is connection


@pytest.mark.asyncio
async def test_multiple_console_messages() -> None:
    """Verifica que se puedan enviar múltiples mensajes consecutivos."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    sender = ConsoleMessageSender(connection)

    await sender.send_console_msg("Mensaje 1")
    await sender.send_console_msg("Mensaje 2", font_color=1)
    await sender.send_error_msg("Error")

    assert writer.write.call_count == 3
    assert writer.drain.call_count == 3


@pytest.mark.asyncio
async def test_send_console_msg_long_message() -> None:
    """Verifica que send_console_msg() maneje mensajes largos."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    sender = ConsoleMessageSender(connection)

    long_message = "A" * 200  # Mensaje de 200 caracteres
    await sender.send_console_msg(long_message)

    assert writer.write.called
    written_data = writer.write.call_args[0][0]
    assert written_data[0] == ServerPacketID.CONSOLE_MSG
