"""Tests para música MIDI."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.client_connection import ClientConnection
from src.messaging.message_sender import MessageSender
from src.packet_id import ServerPacketID
from src.sounds import MusicID


@pytest.mark.asyncio
async def test_send_play_midi() -> None:
    """Verifica que send_play_midi envíe el paquete correcto."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)

    # Enviar música
    await message_sender.send_play_midi(midi_id=2)

    # Verificar que se envió
    assert writer.write.call_count == 1
    sent_data = writer.write.call_args[0][0]

    # Verificar PacketID
    assert sent_data[0] == ServerPacketID.PLAY_MIDI

    # Verificar midi_id (byte 1)
    assert sent_data[1] == 2


@pytest.mark.asyncio
async def test_play_music_main_theme() -> None:
    """Verifica que play_music_main_theme use el ID correcto."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)

    await message_sender.play_music_main_theme()

    assert writer.write.call_count == 1
    sent_data = writer.write.call_args[0][0]

    assert sent_data[0] == ServerPacketID.PLAY_MIDI
    assert sent_data[1] == MusicID.MAIN_THEME


@pytest.mark.asyncio
async def test_play_music_battle() -> None:
    """Verifica que play_music_battle use el ID correcto."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)

    await message_sender.play_music_battle()

    assert writer.write.call_count == 1
    sent_data = writer.write.call_args[0][0]

    assert sent_data[0] == ServerPacketID.PLAY_MIDI
    assert sent_data[1] == MusicID.BATTLE


@pytest.mark.asyncio
async def test_play_music_town() -> None:
    """Verifica que play_music_town use el ID correcto."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)

    await message_sender.play_music_town()

    assert writer.write.call_count == 1
    sent_data = writer.write.call_args[0][0]

    assert sent_data[0] == ServerPacketID.PLAY_MIDI
    assert sent_data[1] == MusicID.TOWN


@pytest.mark.asyncio
async def test_play_music_dungeon() -> None:
    """Verifica que play_music_dungeon use el ID correcto."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)

    await message_sender.play_music_dungeon()

    assert writer.write.call_count == 1
    sent_data = writer.write.call_args[0][0]

    assert sent_data[0] == ServerPacketID.PLAY_MIDI
    assert sent_data[1] == MusicID.DUNGEON


@pytest.mark.asyncio
async def test_music_id_values() -> None:
    """Verifica que los IDs de música tengan valores correctos."""
    assert MusicID.MAIN_THEME == 1
    assert MusicID.BATTLE == 2
    assert MusicID.TOWN == 3
    assert MusicID.DUNGEON == 4
