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


def build_pos_update_response(x: int, y: int) -> bytes:
    """Construye el paquete PosUpdate del protocolo AO estándar.

    Args:
        x: Posición X del personaje (1 byte, 0-255).
        y: Posición Y del personaje (1 byte, 0-255).

    Returns:
        Paquete de bytes con el formato: PacketID (22) + x (1 byte) + y (1 byte).
    """
    packet = PacketBuilder()
    packet.add_byte(ServerPacketID.POS_UPDATE)
    packet.add_byte(x)
    packet.add_byte(y)
    return packet.to_bytes()


def build_error_msg_response(error_message: str) -> bytes:
    """Construye el paquete ErrorMsg del protocolo AO estándar.

    Args:
        error_message: Mensaje de error.

    Returns:
        Paquete de bytes con el formato:
        PacketID (55) + longitud (int16) + mensaje de error (string).
    """
    packet = PacketBuilder()
    packet.add_byte(ServerPacketID.ERROR_MSG)
    encoded_message = error_message.encode("utf-8")
    packet.add_int16(len(encoded_message))
    packet.add_bytes(encoded_message)
    return packet.to_bytes()
