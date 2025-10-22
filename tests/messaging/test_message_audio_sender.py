"""Tests para AudioMessageSender.

Verifica el envío de música y sonidos al cliente.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.messaging.senders.message_audio_sender import AudioMessageSender
from src.network.client_connection import ClientConnection
from src.network.packet_id import ServerPacketID
from src.utils.sounds import MusicID, SoundID


@pytest.mark.asyncio
async def test_send_play_midi() -> None:
    """Verifica que send_play_midi() construya y envíe el paquete correcto."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    sender = AudioMessageSender(connection)

    await sender.send_play_midi(midi_id=5)

    # Verificar que se llamó write
    assert writer.write.called
    written_data = writer.write.call_args[0][0]

    # Verificar estructura: PacketID + midi_id (byte)
    assert len(written_data) == 2
    assert written_data[0] == ServerPacketID.PLAY_MIDI
    assert written_data[1] == 5

    writer.drain.assert_called_once()


@pytest.mark.asyncio
async def test_send_play_wave() -> None:
    """Verifica que send_play_wave() construya y envíe el paquete correcto."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    sender = AudioMessageSender(connection)

    await sender.send_play_wave(wave_id=10, x=50, y=75)

    # Verificar que se llamó write
    assert writer.write.called
    written_data = writer.write.call_args[0][0]

    # Verificar estructura: PacketID + wave_id (byte) + x (byte) + y (byte)
    assert len(written_data) == 4
    assert written_data[0] == ServerPacketID.PLAY_WAVE
    assert written_data[1] == 10  # wave_id
    assert written_data[2] == 50  # x
    assert written_data[3] == 75  # y

    writer.drain.assert_called_once()


@pytest.mark.asyncio
async def test_send_play_wave_global() -> None:
    """Verifica que send_play_wave() maneje sonidos globales (x=0, y=0)."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    sender = AudioMessageSender(connection)

    await sender.send_play_wave(wave_id=1)

    written_data = writer.write.call_args[0][0]

    # Verificar que x e y sean 0 (sonido global)
    assert written_data[2] == 0  # x
    assert written_data[3] == 0  # y


@pytest.mark.asyncio
async def test_play_sound_login() -> None:
    """Verifica que play_sound_login() use el SoundID correcto."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    sender = AudioMessageSender(connection)

    await sender.play_sound_login()

    written_data = writer.write.call_args[0][0]
    assert written_data[0] == ServerPacketID.PLAY_WAVE
    assert written_data[1] == SoundID.LOGIN


@pytest.mark.asyncio
async def test_play_sound_click() -> None:
    """Verifica que play_sound_click() use el SoundID correcto."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    sender = AudioMessageSender(connection)

    await sender.play_sound_click()

    written_data = writer.write.call_args[0][0]
    assert written_data[1] == SoundID.CLICK


@pytest.mark.asyncio
async def test_play_sound_level_up() -> None:
    """Verifica que play_sound_level_up() use el SoundID correcto."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    sender = AudioMessageSender(connection)

    await sender.play_sound_level_up()

    written_data = writer.write.call_args[0][0]
    assert written_data[1] == SoundID.LEVEL_UP


@pytest.mark.asyncio
async def test_play_sound_error() -> None:
    """Verifica que play_sound_error() use el SoundID correcto."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    sender = AudioMessageSender(connection)

    await sender.play_sound_error()

    written_data = writer.write.call_args[0][0]
    assert written_data[1] == SoundID.ERROR


@pytest.mark.asyncio
async def test_play_sound_gold_pickup() -> None:
    """Verifica que play_sound_gold_pickup() use el SoundID correcto."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    sender = AudioMessageSender(connection)

    await sender.play_sound_gold_pickup()

    written_data = writer.write.call_args[0][0]
    assert written_data[1] == SoundID.GOLD_PICKUP


@pytest.mark.asyncio
async def test_play_sound_item_pickup() -> None:
    """Verifica que play_sound_item_pickup() use el SoundID correcto."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    sender = AudioMessageSender(connection)

    await sender.play_sound_item_pickup()

    written_data = writer.write.call_args[0][0]
    assert written_data[1] == SoundID.ITEM_PICKUP


@pytest.mark.asyncio
async def test_play_music_main_theme() -> None:
    """Verifica que play_music_main_theme() use el MusicID correcto."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    sender = AudioMessageSender(connection)

    await sender.play_music_main_theme()

    written_data = writer.write.call_args[0][0]
    assert written_data[0] == ServerPacketID.PLAY_MIDI
    assert written_data[1] == MusicID.MAIN_THEME


@pytest.mark.asyncio
async def test_play_music_battle() -> None:
    """Verifica que play_music_battle() use el MusicID correcto."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    sender = AudioMessageSender(connection)

    await sender.play_music_battle()

    written_data = writer.write.call_args[0][0]
    assert written_data[1] == MusicID.BATTLE


@pytest.mark.asyncio
async def test_play_music_town() -> None:
    """Verifica que play_music_town() use el MusicID correcto."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    sender = AudioMessageSender(connection)

    await sender.play_music_town()

    written_data = writer.write.call_args[0][0]
    assert written_data[1] == MusicID.TOWN


@pytest.mark.asyncio
async def test_play_music_dungeon() -> None:
    """Verifica que play_music_dungeon() use el MusicID correcto."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    sender = AudioMessageSender(connection)

    await sender.play_music_dungeon()

    written_data = writer.write.call_args[0][0]
    assert written_data[1] == MusicID.DUNGEON


@pytest.mark.asyncio
async def test_audio_message_sender_initialization() -> None:
    """Verifica que AudioMessageSender se inicialice correctamente."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("192.168.1.100", 54321)

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    sender = AudioMessageSender(connection)

    assert sender.connection is connection


@pytest.mark.asyncio
async def test_multiple_audio_messages() -> None:
    """Verifica que se puedan enviar múltiples mensajes consecutivos."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    sender = AudioMessageSender(connection)

    await sender.send_play_midi(midi_id=1)
    await sender.send_play_wave(wave_id=2, x=10, y=20)
    await sender.play_sound_login()
    await sender.play_music_main_theme()

    assert writer.write.call_count == 4
    assert writer.drain.call_count == 4
