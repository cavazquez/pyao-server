"""Tests para sonidos WAV."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.client_connection import ClientConnection
from src.message_sender import MessageSender
from src.packet_id import ServerPacketID
from src.sounds import SoundID


@pytest.mark.asyncio
async def test_send_play_wave() -> None:
    """Verifica que send_play_wave envíe el paquete correcto."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)

    # Enviar sonido
    await message_sender.send_play_wave(wave_id=3, x=0, y=0)

    # Verificar que se envió
    assert writer.write.call_count == 1
    sent_data = writer.write.call_args[0][0]

    # Verificar PacketID
    assert sent_data[0] == ServerPacketID.PLAY_WAVE

    # Verificar wave_id (byte 1)
    assert sent_data[1] == 3

    # Verificar x e y (bytes 2 y 3)
    assert sent_data[2] == 0
    assert sent_data[3] == 0


@pytest.mark.asyncio
async def test_play_sound_login() -> None:
    """Verifica que play_sound_login use el ID correcto."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)

    await message_sender.play_sound_login()

    assert writer.write.call_count == 1
    sent_data = writer.write.call_args[0][0]

    assert sent_data[0] == ServerPacketID.PLAY_WAVE
    assert sent_data[1] == SoundID.LOGIN


@pytest.mark.asyncio
async def test_play_sound_error() -> None:
    """Verifica que play_sound_error use el ID correcto."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)

    await message_sender.play_sound_error()

    assert writer.write.call_count == 1
    sent_data = writer.write.call_args[0][0]

    assert sent_data[0] == ServerPacketID.PLAY_WAVE
    assert sent_data[1] == SoundID.ERROR


@pytest.mark.asyncio
async def test_play_sound_click() -> None:
    """Verifica que play_sound_click use el ID correcto."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)

    await message_sender.play_sound_click()

    assert writer.write.call_count == 1
    sent_data = writer.write.call_args[0][0]

    assert sent_data[0] == ServerPacketID.PLAY_WAVE
    assert sent_data[1] == SoundID.CLICK


@pytest.mark.asyncio
async def test_play_sound_level_up() -> None:
    """Verifica que play_sound_level_up use el ID correcto."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)

    await message_sender.play_sound_level_up()

    assert writer.write.call_count == 1
    sent_data = writer.write.call_args[0][0]

    assert sent_data[0] == ServerPacketID.PLAY_WAVE
    assert sent_data[1] == SoundID.LEVEL_UP


@pytest.mark.asyncio
async def test_sound_id_values() -> None:
    """Verifica que los IDs de sonido tengan valores correctos."""
    assert SoundID.LOGIN == 3
    assert SoundID.LOGOUT == 4
    assert SoundID.CLICK == 5
    assert SoundID.LEVEL_UP == 60
    assert SoundID.ERROR == 62
