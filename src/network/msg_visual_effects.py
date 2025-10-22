"""Construcción de mensajes de efectos visuales."""

from src.network.packet_builder import PacketBuilder
from src.network.packet_id import ServerPacketID


def build_create_fx_response(char_index: int, fx: int, loops: int) -> bytes:
    """Construye el paquete CreateFX del protocolo AO estándar.

    Args:
        char_index: ID del personaje/objeto que genera el efecto (int16).
        fx: ID del efecto visual (int16).
        loops: Número de loops (int16). -1 = infinito, 0 = una vez, >0 = número específico.

    Returns:
        Paquete de bytes: PacketID (44) + charIndex (int16) + fx (int16) + loops (int16).
    """
    packet = PacketBuilder()
    packet.add_byte(ServerPacketID.CREATE_FX)
    packet.add_int16(char_index)
    packet.add_int16(fx)
    packet.add_int16(loops)
    return packet.to_bytes()
