"""Construcción de mensajes de audio."""

from src.network.packet_builder import PacketBuilder
from src.network.packet_id import ServerPacketID


def build_play_midi_response(midi_id: int) -> bytes:
    """Construye el paquete PlayMIDI del protocolo AO estándar.

    Args:
        midi_id: ID de la música MIDI a reproducir (byte).

    Returns:
        Paquete de bytes con el formato: PacketID (38) + midi (1 byte).
    """
    packet = PacketBuilder()
    packet.add_byte(ServerPacketID.PLAY_MIDI)
    packet.add_byte(midi_id)
    return packet.to_bytes()


def build_play_wave_response(wave_id: int, x: int = 0, y: int = 0) -> bytes:
    """Construye el paquete PlayWave del protocolo AO estándar.

    Args:
        wave_id: ID del sonido a reproducir (byte).
        x: Posición X del sonido (byte), 0 para sonido global.
        y: Posición Y del sonido (byte), 0 para sonido global.

    Returns:
        Paquete de bytes con el formato: PacketID (39) + wave (1 byte) + x (1 byte) + y (1 byte).
    """
    packet = PacketBuilder()
    packet.add_byte(ServerPacketID.PLAY_WAVE)
    packet.add_byte(wave_id)
    packet.add_byte(x)
    packet.add_byte(y)
    return packet.to_bytes()
