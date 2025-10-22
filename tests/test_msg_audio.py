"""Tests para msg_audio.py."""

from src.network.msg_audio import build_play_midi_response, build_play_wave_response
from src.network.packet_id import ServerPacketID


def test_build_play_midi_response() -> None:
    """Verifica que build_play_midi_response construye el paquete correctamente."""
    response = build_play_midi_response(midi_id=5)

    assert isinstance(response, bytes)
    assert len(response) == 2  # 1 byte PacketID + 1 byte midi_id
    assert response[0] == ServerPacketID.PLAY_MIDI
    assert response[1] == 5


def test_build_play_wave_response() -> None:
    """Verifica que build_play_wave_response construye el paquete correctamente."""
    response = build_play_wave_response(wave_id=10, x=50, y=47)

    assert isinstance(response, bytes)
    assert len(response) == 4  # 1 byte PacketID + 1 byte wave + 1 byte x + 1 byte y
    assert response[0] == ServerPacketID.PLAY_WAVE
    assert response[1] == 10
    assert response[2] == 50
    assert response[3] == 47


def test_build_play_wave_response_global() -> None:
    """Verifica que build_play_wave_response con posición global (0,0)."""
    response = build_play_wave_response(wave_id=3)

    assert isinstance(response, bytes)
    assert response[2] == 0  # x = 0
    assert response[3] == 0  # y = 0
