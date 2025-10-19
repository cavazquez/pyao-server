"""Construcción de mensajes de sesión y login."""

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


def build_attributes_response(
    strength: int,
    agility: int,
    intelligence: int,
    charisma: int,
    constitution: int,
) -> bytes:
    """Construye el paquete de respuesta con los atributos del personaje.

    Args:
        strength: Valor de fuerza.
        agility: Valor de agilidad.
        intelligence: Valor de inteligencia.
        charisma: Valor de carisma.
        constitution: Valor de constitución.

    Returns:
        Paquete de bytes con el formato: PacketID (50) + 5 bytes de atributos.
    """
    packet = PacketBuilder()
    packet.add_byte(ServerPacketID.ATTRIBUTES)
    packet.add_byte(strength)
    packet.add_byte(agility)
    packet.add_byte(intelligence)
    packet.add_byte(charisma)
    packet.add_byte(constitution)
    return packet.to_bytes()


def build_logged_response(user_class: int) -> bytes:
    """Construye el paquete Logged del protocolo AO estándar.

    Args:
        user_class: Clase del personaje (1 byte).

    Returns:
        Paquete de bytes con el formato: PacketID (0) + userClass (1 byte).
    """
    packet = PacketBuilder()
    packet.add_byte(ServerPacketID.LOGGED)
    packet.add_byte(user_class)
    return packet.to_bytes()


def build_user_char_index_in_server_response(char_index: int) -> bytes:
    """Construye el paquete UserCharIndexInServer del protocolo AO estándar.

    Args:
        char_index: Índice del personaje del jugador en el servidor (int16).

    Returns:
        Paquete de bytes con el formato: PacketID (28) + charIndex (int16).
    """
    packet = PacketBuilder()
    packet.add_byte(ServerPacketID.USER_CHAR_INDEX_IN_SERVER)
    packet.add_int16(char_index)
    return packet.to_bytes()
