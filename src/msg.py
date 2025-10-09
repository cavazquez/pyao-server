"""Construcción de mensajes/paquetes del servidor."""

from src.packet_builder import PacketBuilder
from src.packet_id import ServerPacketID


def build_dice_roll_response(
    strength: int,
    agility: int,
    intelligence: int,
    charisma: int,
    constitution: int,
) -> bytes:
    """Construye el paquete de respuesta para la tirada de dados.

    Args:
        strength: Valor de fuerza (6-18).
        agility: Valor de agilidad (6-18).
        intelligence: Valor de inteligencia (6-18).
        charisma: Valor de carisma (6-18).
        constitution: Valor de constitución (6-18).

    Returns:
        Paquete de bytes con el formato: PacketID + 5 bytes de atributos.
    """
    packet = PacketBuilder()
    packet.add_byte(ServerPacketID.DICE_ROLL)
    packet.add_byte(strength)
    packet.add_byte(agility)
    packet.add_byte(intelligence)
    packet.add_byte(charisma)
    packet.add_byte(constitution)
    return packet.to_bytes()
