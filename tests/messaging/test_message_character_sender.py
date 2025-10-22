"""Tests para CharacterMessageSender.

Verifica el envío de información de personajes al cliente.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.network.client_connection import ClientConnection
from src.messaging.senders.message_character_sender import CharacterMessageSender
from src.network.packet_id import ServerPacketID


@pytest.mark.asyncio
async def test_send_character_create() -> None:
    """Verifica que send_character_create() construya y envíe el paquete correcto."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    sender = CharacterMessageSender(connection)

    await sender.send_character_create(
        char_index=100,
        body=1,
        head=2,
        heading=3,
        x=50,
        y=75,
        weapon=10,
        shield=20,
        helmet=30,
        fx=5,
        loops=1,
        name="TestPlayer",
    )

    # Verificar que se llamó write
    assert writer.write.called
    written_data = writer.write.call_args[0][0]

    # Verificar que sea CHARACTER_CREATE
    assert written_data[0] == ServerPacketID.CHARACTER_CREATE
    # Verificar que el nombre esté en los datos
    name_bytes = b"TestPlayer"
    assert name_bytes in written_data

    writer.drain.assert_called_once()


@pytest.mark.asyncio
async def test_send_character_create_with_long_name() -> None:
    """Verifica que send_character_create() maneje nombres largos."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    sender = CharacterMessageSender(connection)

    long_name = "VeryLongPlayerName123"
    await sender.send_character_create(
        char_index=200,
        body=1,
        head=1,
        heading=1,
        x=10,
        y=20,
        weapon=0,
        shield=0,
        helmet=0,
        fx=0,
        loops=0,
        name=long_name,
    )

    written_data = writer.write.call_args[0][0]
    assert written_data[0] == ServerPacketID.CHARACTER_CREATE
    name_bytes = long_name.encode("utf-8")
    assert name_bytes in written_data


@pytest.mark.asyncio
async def test_send_character_change() -> None:
    """Verifica que send_character_change() construya y envíe el paquete correcto."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    sender = CharacterMessageSender(connection)

    await sender.send_character_change(
        char_index=150, body=5, head=6, heading=2, weapon=15, shield=25, helmet=35, fx=10, loops=2
    )

    # Verificar que se llamó write
    assert writer.write.called
    written_data = writer.write.call_args[0][0]

    # Verificar que sea CHARACTER_CHANGE
    assert written_data[0] == ServerPacketID.CHARACTER_CHANGE

    writer.drain.assert_called_once()


@pytest.mark.asyncio
async def test_send_character_change_with_defaults() -> None:
    """Verifica que send_character_change() use valores por defecto."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    sender = CharacterMessageSender(connection)

    # Solo especificar char_index, el resto usa defaults (0)
    await sender.send_character_change(char_index=100)

    written_data = writer.write.call_args[0][0]
    assert written_data[0] == ServerPacketID.CHARACTER_CHANGE


@pytest.mark.asyncio
async def test_send_character_remove() -> None:
    """Verifica que send_character_remove() construya y envíe el paquete correcto."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    sender = CharacterMessageSender(connection)

    await sender.send_character_remove(char_index=250)

    # Verificar que se llamó write
    assert writer.write.called
    written_data = writer.write.call_args[0][0]

    # Verificar estructura: PacketID + char_index (int16 LE)
    assert written_data[0] == ServerPacketID.CHARACTER_REMOVE
    # char_index = 250 (little-endian int16)
    assert written_data[1] == 250
    assert written_data[2] == 0

    writer.drain.assert_called_once()


@pytest.mark.asyncio
async def test_send_character_move() -> None:
    """Verifica que send_character_move() construya y envíe el paquete correcto."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    sender = CharacterMessageSender(connection)

    await sender.send_character_move(char_index=300, x=60, y=80)

    # Verificar que se llamó write
    assert writer.write.called
    written_data = writer.write.call_args[0][0]

    # Verificar estructura: PacketID + char_index (int16 LE) + x (byte) + y (byte)
    assert written_data[0] == ServerPacketID.CHARACTER_MOVE
    # char_index = 300 (little-endian int16)
    assert written_data[1] == 44  # 300 & 0xFF
    assert written_data[2] == 1  # (300 >> 8) & 0xFF
    # x, y
    assert written_data[3] == 60
    assert written_data[4] == 80

    writer.drain.assert_called_once()


@pytest.mark.asyncio
async def test_character_message_sender_initialization() -> None:
    """Verifica que CharacterMessageSender se inicialice correctamente."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("192.168.1.100", 54321)

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    sender = CharacterMessageSender(connection)

    assert sender.connection is connection


@pytest.mark.asyncio
async def test_multiple_character_messages() -> None:
    """Verifica que se puedan enviar múltiples mensajes consecutivos."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    sender = CharacterMessageSender(connection)

    await sender.send_character_create(
        char_index=1,
        body=1,
        head=1,
        heading=1,
        x=10,
        y=10,
        weapon=0,
        shield=0,
        helmet=0,
        fx=0,
        loops=0,
        name="Player1",
    )
    await sender.send_character_change(char_index=1, heading=2)
    await sender.send_character_move(char_index=1, x=11, y=10)
    await sender.send_character_remove(char_index=1)

    assert writer.write.call_count == 4
    assert writer.drain.call_count == 4
