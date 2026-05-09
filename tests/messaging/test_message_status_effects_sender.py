"""Tests para StatusEffectsMessageSender.

Verifica el envío de mensajes de efectos de estado al cliente.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.messaging.senders.message_status_effects_sender import StatusEffectsMessageSender
from src.network.client_connection import ClientConnection
from src.network.packet_id import ServerPacketID


def _create_connection() -> tuple[ClientConnection, MagicMock]:
    """Crea una conexión mock para tests."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()
    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    return connection, writer


@pytest.mark.asyncio
async def test_send_blind() -> None:
    """Verifica que send_blind() envíe el paquete BLIND (sin datos adicionales)."""
    connection, writer = _create_connection()
    sender = StatusEffectsMessageSender(connection)

    await sender.send_blind()

    assert writer.write.called
    written_data = writer.write.call_args[0][0]
    assert written_data == bytes([ServerPacketID.BLIND])
    writer.drain.assert_called_once()


@pytest.mark.asyncio
async def test_send_blind_no_more() -> None:
    """Verifica que send_blind_no_more() envíe el paquete BLIND_NO_MORE."""
    connection, writer = _create_connection()
    sender = StatusEffectsMessageSender(connection)

    await sender.send_blind_no_more()

    assert writer.write.called
    written_data = writer.write.call_args[0][0]
    assert written_data == bytes([ServerPacketID.BLIND_NO_MORE])
    writer.drain.assert_called_once()


@pytest.mark.asyncio
async def test_send_dumb() -> None:
    """Verifica que send_dumb() envíe el paquete DUMB."""
    connection, writer = _create_connection()
    sender = StatusEffectsMessageSender(connection)

    await sender.send_dumb()

    assert writer.write.called
    written_data = writer.write.call_args[0][0]
    assert written_data == bytes([ServerPacketID.DUMB])
    writer.drain.assert_called_once()


@pytest.mark.asyncio
async def test_send_dumb_no_more() -> None:
    """Verifica que send_dumb_no_more() envíe el paquete DUMB_NO_MORE."""
    connection, writer = _create_connection()
    sender = StatusEffectsMessageSender(connection)

    await sender.send_dumb_no_more()

    assert writer.write.called
    written_data = writer.write.call_args[0][0]
    assert written_data == bytes([ServerPacketID.DUMB_NO_MORE])
    writer.drain.assert_called_once()


@pytest.mark.asyncio
async def test_send_paralize_ok() -> None:
    """Verifica que send_paralize_ok() envíe el paquete PARALIZE_OK."""
    connection, writer = _create_connection()
    sender = StatusEffectsMessageSender(connection)

    await sender.send_paralize_ok()

    assert writer.write.called
    written_data = writer.write.call_args[0][0]
    assert written_data == bytes([ServerPacketID.PARALIZE_OK])
    writer.drain.assert_called_once()


@pytest.mark.asyncio
async def test_send_rest_ok() -> None:
    """Verifica que send_rest_ok() envíe el paquete REST_OK."""
    connection, writer = _create_connection()
    sender = StatusEffectsMessageSender(connection)

    await sender.send_rest_ok()

    assert writer.write.called
    written_data = writer.write.call_args[0][0]
    assert written_data == bytes([ServerPacketID.REST_OK])
    writer.drain.assert_called_once()


@pytest.mark.asyncio
async def test_send_set_invisible_visible() -> None:
    """Verifica que send_set_invisible() con invisible=True envíe el formato correcto."""
    connection, writer = _create_connection()
    sender = StatusEffectsMessageSender(connection)

    await sender.send_set_invisible(char_index=42, invisible=True)

    assert writer.write.called
    written_data = writer.write.call_args[0][0]
    assert written_data[0] == ServerPacketID.SET_INVISIBLE
    # charIndex en little-endian (42 = 0x002A)
    assert written_data[1] == 42  # low byte
    assert written_data[2] == 0  # high byte
    # invisible=1 (True)
    assert written_data[3] == 1
    writer.drain.assert_called_once()


@pytest.mark.asyncio
async def test_send_set_invisible_not_invisible() -> None:
    """Verifica que send_set_invisible() con invisible=False envíe byte 0."""
    connection, writer = _create_connection()
    sender = StatusEffectsMessageSender(connection)

    await sender.send_set_invisible(char_index=5, invisible=False)

    written_data = writer.write.call_args[0][0]
    assert written_data[0] == ServerPacketID.SET_INVISIBLE
    assert written_data[1] == 5  # charIndex low byte
    assert written_data[2] == 0  # charIndex high byte
    assert written_data[3] == 0  # invisible=0


@pytest.mark.asyncio
async def test_send_update_tag_and_status() -> None:
    """Verifica que send_update_tag_and_status() envíe el formato correcto."""
    connection, writer = _create_connection()
    sender = StatusEffectsMessageSender(connection)

    await sender.send_update_tag_and_status(char_index=10, nick_color=1, user_tag="TestPlayer")

    written_data = writer.write.call_args[0][0]
    assert written_data[0] == ServerPacketID.UPDATE_TAG_AND_STATUS

    # charIndex en little-endian (10)
    assert written_data[1] == 10
    assert written_data[2] == 0

    # nickColor
    assert written_data[3] == 1

    # userTag como unicode string (len + latin-1 bytes)
    tag_bytes = "TestPlayer".encode("latin-1", errors="replace")
    tag_len = int.from_bytes(written_data[4:6], byteorder="little", signed=True)
    assert tag_len == len(tag_bytes)
    assert written_data[6 : 6 + tag_len] == tag_bytes

    writer.drain.assert_called_once()


@pytest.mark.asyncio
async def test_send_update_tag_and_status_with_empty_tag() -> None:
    """Verifica UPDATE_TAG_AND_STATUS con tag vacío."""
    connection, writer = _create_connection()
    sender = StatusEffectsMessageSender(connection)

    await sender.send_update_tag_and_status(char_index=3, nick_color=0, user_tag="")

    written_data = writer.write.call_args[0][0]
    assert written_data[0] == ServerPacketID.UPDATE_TAG_AND_STATUS
    assert written_data[3] == 0  # nickColor=0

    # String vacío: len=0
    tag_len = int.from_bytes(written_data[4:6], byteorder="little", signed=True)
    assert tag_len == 0
