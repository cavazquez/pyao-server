"""Tests para efectos visuales FX."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.client_connection import ClientConnection
from src.messaging.message_sender import MessageSender
from src.packet_id import ServerPacketID
from src.visual_effects import FXLoops, VisualEffectID


@pytest.mark.asyncio
async def test_send_create_fx() -> None:
    """Verifica que send_create_fx envíe el paquete correcto."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)

    # Enviar efecto
    await message_sender.send_create_fx(char_index=123, fx=3, loops=1)

    # Verificar que se envió
    assert writer.write.call_count == 1
    sent_data = writer.write.call_args[0][0]

    # Verificar PacketID
    assert sent_data[0] == ServerPacketID.CREATE_FX

    # Verificar char_index (bytes 1-2, int16 little-endian)
    assert sent_data[1] == 123
    assert sent_data[2] == 0

    # Verificar fx (bytes 3-4, int16 little-endian)
    assert sent_data[3] == 3
    assert sent_data[4] == 0

    # Verificar loops (bytes 5-6, int16 little-endian)
    assert sent_data[5] == 1
    assert sent_data[6] == 0


@pytest.mark.asyncio
async def test_play_effect_spawn() -> None:
    """Verifica que play_effect_spawn use los valores correctos."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)

    await message_sender.play_effect_spawn(char_index=456)

    assert writer.write.call_count == 1
    sent_data = writer.write.call_args[0][0]

    assert sent_data[0] == ServerPacketID.CREATE_FX

    # Verificar char_index
    assert sent_data[1] == 200  # 456 % 256
    assert sent_data[2] == 1  # 456 // 256

    # Verificar fx = SPAWN_BLUE (1)
    assert sent_data[3] == VisualEffectID.SPAWN_BLUE
    assert sent_data[4] == 0

    # Verificar loops = ONCE (1)
    assert sent_data[5] == FXLoops.ONCE
    assert sent_data[6] == 0


@pytest.mark.asyncio
async def test_play_effect_heal() -> None:
    """Verifica que play_effect_heal use los valores correctos."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)

    await message_sender.play_effect_heal(char_index=100)

    assert writer.write.call_count == 1
    sent_data = writer.write.call_args[0][0]

    assert sent_data[0] == ServerPacketID.CREATE_FX
    assert sent_data[3] == VisualEffectID.HEAL
    assert sent_data[5] == FXLoops.ONCE


@pytest.mark.asyncio
async def test_play_effect_meditation() -> None:
    """Verifica que play_effect_meditation use loops infinitos."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)

    await message_sender.play_effect_meditation(char_index=100)

    assert writer.write.call_count == 1
    sent_data = writer.write.call_args[0][0]

    assert sent_data[0] == ServerPacketID.CREATE_FX
    assert sent_data[3] == VisualEffectID.MEDITATION
    assert sent_data[5] == FXLoops.INFINITE  # 0 = infinito


@pytest.mark.asyncio
async def test_play_effect_explosion() -> None:
    """Verifica que play_effect_explosion use los valores correctos."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)

    await message_sender.play_effect_explosion(char_index=200)

    assert writer.write.call_count == 1
    sent_data = writer.write.call_args[0][0]

    assert sent_data[0] == ServerPacketID.CREATE_FX
    assert sent_data[3] == VisualEffectID.EXPLOSION
    assert sent_data[5] == FXLoops.ONCE


@pytest.mark.asyncio
async def test_visual_effect_id_values() -> None:
    """Verifica que los IDs de efectos visuales tengan valores correctos."""
    assert VisualEffectID.SPAWN_BLUE == 1
    assert VisualEffectID.SPAWN_RED == 2
    assert VisualEffectID.SPAWN_YELLOW == 3
    assert VisualEffectID.SPAWN_GREEN == 4
    assert VisualEffectID.HEAL == 7
    assert VisualEffectID.MEDITATION == 22


@pytest.mark.asyncio
async def test_fx_loops_values() -> None:
    """Verifica que los valores de loops sean correctos."""
    assert FXLoops.ONCE == 1
    assert FXLoops.INFINITE == 0
