"""Tests para MapMessageSender.

Verifica el envío de información de mapa y posición al cliente.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.client_connection import ClientConnection
from src.message_map_sender import MapMessageSender
from src.packet_id import ServerPacketID


@pytest.mark.asyncio
async def test_send_change_map() -> None:
    """Verifica que send_change_map() construya y envíe el paquete correcto."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    sender = MapMessageSender(connection)

    await sender.send_change_map(map_number=5, version=10)

    # Verificar que se llamó write
    assert writer.write.called
    written_data = writer.write.call_args[0][0]

    # Verificar estructura: PacketID + map_number (int16 LE) + version (int16 LE)
    assert len(written_data) == 5
    assert written_data[0] == ServerPacketID.CHANGE_MAP
    # map_number = 5 (little-endian int16)
    assert written_data[1] == 5
    assert written_data[2] == 0
    # version = 10 (little-endian int16)
    assert written_data[3] == 10
    assert written_data[4] == 0

    writer.drain.assert_called_once()


@pytest.mark.asyncio
async def test_send_change_map_default_version() -> None:
    """Verifica que send_change_map() use version=0 por defecto."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    sender = MapMessageSender(connection)

    await sender.send_change_map(map_number=1)

    written_data = writer.write.call_args[0][0]

    # Verificar que version sea 0
    assert written_data[3] == 0
    assert written_data[4] == 0


@pytest.mark.asyncio
async def test_send_pos_update() -> None:
    """Verifica que send_pos_update() construya y envíe el paquete correcto."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    sender = MapMessageSender(connection)

    await sender.send_pos_update(x=50, y=75)

    # Verificar que se llamó write
    assert writer.write.called
    written_data = writer.write.call_args[0][0]

    # Verificar estructura: PacketID + x (u8) + y (u8)
    assert len(written_data) == 3
    assert written_data[0] == ServerPacketID.POS_UPDATE
    assert written_data[1] == 50  # x
    assert written_data[2] == 75  # y

    writer.drain.assert_called_once()


@pytest.mark.asyncio
async def test_send_object_create() -> None:
    """Verifica que send_object_create() construya y envíe el paquete correcto."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    sender = MapMessageSender(connection)

    await sender.send_object_create(x=25, y=30, grh_index=1234)

    # Verificar que se llamó write
    assert writer.write.called
    written_data = writer.write.call_args[0][0]

    # Verificar estructura: PacketID + x (u8) + y (u8) + grh_index (int16 LE)
    assert len(written_data) == 5
    assert written_data[0] == ServerPacketID.OBJECT_CREATE
    assert written_data[1] == 25  # x
    assert written_data[2] == 30  # y
    # grh_index = 1234 (little-endian int16)
    assert written_data[3] == 210  # 1234 & 0xFF
    assert written_data[4] == 4  # (1234 >> 8) & 0xFF

    writer.drain.assert_called_once()


@pytest.mark.asyncio
async def test_send_object_delete() -> None:
    """Verifica que send_object_delete() construya y envíe el paquete correcto."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    sender = MapMessageSender(connection)

    await sender.send_object_delete(x=40, y=60)

    # Verificar que se llamó write
    assert writer.write.called
    written_data = writer.write.call_args[0][0]

    # Verificar estructura: PacketID + x (u8) + y (u8)
    assert len(written_data) == 3
    assert written_data[0] == ServerPacketID.OBJECT_DELETE
    assert written_data[1] == 40  # x
    assert written_data[2] == 60  # y

    writer.drain.assert_called_once()


@pytest.mark.asyncio
async def test_send_block_position_blocked() -> None:
    """Verifica que send_block_position() envíe correctamente cuando blocked=True."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    sender = MapMessageSender(connection)

    await sender.send_block_position(x=10, y=20, blocked=True)

    # Verificar que se llamó write
    assert writer.write.called
    written_data = writer.write.call_args[0][0]

    # Verificar estructura: PacketID + x (u8) + y (u8) + blocked (u8)
    assert len(written_data) == 4
    assert written_data[0] == ServerPacketID.BLOCK_POSITION
    assert written_data[1] == 10  # x
    assert written_data[2] == 20  # y
    assert written_data[3] == 1  # blocked = True

    writer.drain.assert_called_once()


@pytest.mark.asyncio
async def test_send_block_position_unblocked() -> None:
    """Verifica que send_block_position() envíe correctamente cuando blocked=False."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    sender = MapMessageSender(connection)

    await sender.send_block_position(x=15, y=25, blocked=False)

    written_data = writer.write.call_args[0][0]

    # Verificar que blocked sea 0
    assert written_data[3] == 0  # blocked = False


@pytest.mark.asyncio
async def test_map_message_sender_initialization() -> None:
    """Verifica que MapMessageSender se inicialice correctamente."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("192.168.1.100", 54321)

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    sender = MapMessageSender(connection)

    assert sender.connection is connection


@pytest.mark.asyncio
async def test_multiple_map_messages() -> None:
    """Verifica que se puedan enviar múltiples mensajes consecutivos."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    sender = MapMessageSender(connection)

    await sender.send_change_map(map_number=1)
    await sender.send_pos_update(x=50, y=50)
    await sender.send_object_create(x=25, y=25, grh_index=100)
    await sender.send_object_delete(x=30, y=30)
    await sender.send_block_position(x=10, y=10, blocked=True)

    assert writer.write.call_count == 5
    assert writer.drain.call_count == 5
