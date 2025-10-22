"""Tests para VisualEffectsMessageSender.

Verifica el envío de efectos visuales al cliente.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.client_connection import ClientConnection
from src.messaging.senders.message_visual_effects_sender import VisualEffectsMessageSender
from src.packet_id import ServerPacketID


@pytest.mark.asyncio
async def test_send_create_fx() -> None:
    """Verifica que send_create_fx() construya y envíe el paquete correcto."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    sender = VisualEffectsMessageSender(connection)

    await sender.send_create_fx(char_index=100, fx=5, loops=3)

    # Verificar que se llamó write
    assert writer.write.called
    written_data = writer.write.call_args[0][0]

    # Verificar estructura: PacketID + char_index (int16 LE) + fx (int16 LE) + loops (int16 LE)
    assert written_data[0] == ServerPacketID.CREATE_FX
    # char_index = 100 (little-endian int16)
    assert written_data[1] == 100
    assert written_data[2] == 0
    # fx = 5
    assert written_data[3] == 5
    assert written_data[4] == 0
    # loops = 3
    assert written_data[5] == 3
    assert written_data[6] == 0

    writer.drain.assert_called_once()


@pytest.mark.asyncio
async def test_send_create_fx_infinite_loops() -> None:
    """Verifica que send_create_fx() maneje loops infinitos (-1)."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    sender = VisualEffectsMessageSender(connection)

    await sender.send_create_fx(char_index=50, fx=10, loops=-1)

    written_data = writer.write.call_args[0][0]
    assert written_data[0] == ServerPacketID.CREATE_FX


@pytest.mark.asyncio
async def test_send_create_fx_at_position() -> None:
    """Verifica que send_create_fx_at_position() delegue a send_create_fx."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    sender = VisualEffectsMessageSender(connection)

    await sender.send_create_fx_at_position(_x=50, _y=75, fx=15, loops=2)

    # Verificar que se llamó write
    assert writer.write.called
    written_data = writer.write.call_args[0][0]

    # Debe usar char_index=0 para efectos en el terreno
    assert written_data[0] == ServerPacketID.CREATE_FX
    assert written_data[1] == 0  # char_index = 0
    assert written_data[2] == 0


@pytest.mark.asyncio
async def test_play_effect_spawn() -> None:
    """Verifica que play_effect_spawn() use el efecto correcto."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    sender = VisualEffectsMessageSender(connection)

    await sender.play_effect_spawn(char_index=123)

    written_data = writer.write.call_args[0][0]
    assert written_data[0] == ServerPacketID.CREATE_FX
    # Verificar char_index = 123
    assert written_data[1] == 123
    assert written_data[2] == 0


@pytest.mark.asyncio
async def test_play_effect_heal() -> None:
    """Verifica que play_effect_heal() use el efecto correcto."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    sender = VisualEffectsMessageSender(connection)

    await sender.play_effect_heal(char_index=456)

    written_data = writer.write.call_args[0][0]
    assert written_data[0] == ServerPacketID.CREATE_FX
    # Verificar char_index = 456
    assert written_data[1] == 200  # 456 & 0xFF
    assert written_data[2] == 1  # (456 >> 8) & 0xFF


@pytest.mark.asyncio
async def test_play_effect_meditation() -> None:
    """Verifica que play_effect_meditation() use loops infinitos."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    sender = VisualEffectsMessageSender(connection)

    await sender.play_effect_meditation(char_index=789)

    written_data = writer.write.call_args[0][0]
    assert written_data[0] == ServerPacketID.CREATE_FX
    # Verificar char_index = 789
    assert written_data[1] == 21  # 789 & 0xFF
    assert written_data[2] == 3  # (789 >> 8) & 0xFF


@pytest.mark.asyncio
async def test_play_effect_explosion() -> None:
    """Verifica que play_effect_explosion() use el efecto correcto."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    sender = VisualEffectsMessageSender(connection)

    await sender.play_effect_explosion(char_index=999)

    written_data = writer.write.call_args[0][0]
    assert written_data[0] == ServerPacketID.CREATE_FX
    # Verificar char_index = 999
    assert written_data[1] == 231  # 999 & 0xFF
    assert written_data[2] == 3  # (999 >> 8) & 0xFF


@pytest.mark.asyncio
async def test_visual_effects_message_sender_initialization() -> None:
    """Verifica que VisualEffectsMessageSender se inicialice correctamente."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("192.168.1.100", 54321)

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    sender = VisualEffectsMessageSender(connection)

    assert sender.connection is connection


@pytest.mark.asyncio
async def test_multiple_visual_effects() -> None:
    """Verifica que se puedan enviar múltiples efectos consecutivos."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    sender = VisualEffectsMessageSender(connection)

    await sender.send_create_fx(char_index=1, fx=5, loops=1)
    await sender.send_create_fx_at_position(_x=10, _y=20, fx=10, loops=2)
    await sender.play_effect_spawn(char_index=100)
    await sender.play_effect_heal(char_index=200)

    assert writer.write.call_count == 4
    assert writer.drain.call_count == 4
