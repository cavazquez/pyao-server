"""Tests para SessionMessageSender.

Verifica el envío de mensajes de sesión y login al cliente.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.messaging.senders.message_session_sender import SessionMessageSender
from src.network.client_connection import ClientConnection
from src.network.packet_id import ServerPacketID


@pytest.mark.asyncio
async def test_send_dice_roll() -> None:
    """Verifica que send_dice_roll() construya y envíe el paquete correcto."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    sender = SessionMessageSender(connection)

    await sender.send_dice_roll(
        strength=15, agility=12, intelligence=14, charisma=10, constitution=16
    )

    # Verificar que se llamó write
    assert writer.write.called
    written_data = writer.write.call_args[0][0]

    # Verificar estructura: PacketID + 5 bytes de atributos
    assert len(written_data) == 6
    assert written_data[0] == ServerPacketID.DICE_ROLL
    assert written_data[1] == 15  # strength
    assert written_data[2] == 12  # agility
    assert written_data[3] == 14  # intelligence
    assert written_data[4] == 10  # charisma
    assert written_data[5] == 16  # constitution

    writer.drain.assert_called_once()


@pytest.mark.asyncio
async def test_send_attributes() -> None:
    """Verifica que send_attributes() construya y envíe el paquete correcto."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    sender = SessionMessageSender(connection)

    await sender.send_attributes(
        strength=18, agility=16, intelligence=12, charisma=14, constitution=15
    )

    written_data = writer.write.call_args[0][0]

    # Verificar estructura: PacketID + 5 bytes de atributos
    assert len(written_data) == 6
    assert written_data[0] == ServerPacketID.ATTRIBUTES
    assert written_data[1] == 18  # strength
    assert written_data[2] == 16  # agility
    assert written_data[3] == 12  # intelligence
    assert written_data[4] == 14  # charisma
    assert written_data[5] == 15  # constitution


@pytest.mark.asyncio
async def test_send_logged() -> None:
    """Verifica que send_logged() construya y envíe el paquete correcto."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    sender = SessionMessageSender(connection)

    await sender.send_logged(user_class=1)

    written_data = writer.write.call_args[0][0]

    # Verificar estructura: PacketID + user_class (byte)
    assert len(written_data) == 2
    assert written_data[0] == ServerPacketID.LOGGED
    assert written_data[1] == 1  # user_class


@pytest.mark.asyncio
async def test_send_user_char_index_in_server() -> None:
    """Verifica que send_user_char_index_in_server() construya el paquete correcto."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    sender = SessionMessageSender(connection)

    await sender.send_user_char_index_in_server(char_index=100)

    written_data = writer.write.call_args[0][0]

    # Verificar estructura: PacketID + char_index (int16 LE)
    assert written_data[0] == ServerPacketID.USER_CHAR_INDEX_IN_SERVER
    # char_index = 100 (little-endian int16)
    assert written_data[1] == 100
    assert written_data[2] == 0


@pytest.mark.asyncio
async def test_session_message_sender_initialization() -> None:
    """Verifica que SessionMessageSender se inicialice correctamente."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("192.168.1.100", 54321)

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    sender = SessionMessageSender(connection)

    assert sender.connection is connection


@pytest.mark.asyncio
async def test_multiple_session_messages() -> None:
    """Verifica que se puedan enviar múltiples mensajes consecutivos."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    sender = SessionMessageSender(connection)

    await sender.send_dice_roll(10, 10, 10, 10, 10)
    await sender.send_attributes(15, 15, 15, 15, 15)
    await sender.send_logged(user_class=2)
    await sender.send_user_char_index_in_server(char_index=50)

    assert writer.write.call_count == 4
    assert writer.drain.call_count == 4
