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


def build_account_created_response(user_id: int) -> bytes:
    """Construye el paquete de respuesta para cuenta creada exitosamente.

    Args:
        user_id: ID del usuario creado.

    Returns:
        Paquete de bytes con el formato: PacketID + user_id (int32).
    """
    packet = PacketBuilder()
    packet.add_byte(ServerPacketID.ACCOUNT_CREATED)
    packet.add_int32(user_id)
    return packet.to_bytes()


def build_account_error_response(error_message: str) -> bytes:
    """Construye el paquete de respuesta para error en creación de cuenta.

    Args:
        error_message: Mensaje de error.

    Returns:
        Paquete de bytes con el formato: PacketID + longitud (int16) + mensaje de error (string).
    """
    packet = PacketBuilder()
    packet.add_byte(ServerPacketID.ACCOUNT_ERROR)
    # Agregar longitud del string como int16 antes del contenido
    encoded_message = error_message.encode("utf-8")
    packet.add_int16(len(encoded_message))
    packet.add_bytes(encoded_message)
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
        Paquete de bytes con el formato: PacketID + 5 bytes de atributos.
    """
    packet = PacketBuilder()
    packet.add_byte(ServerPacketID.ATTRIBUTES)
    packet.add_byte(strength)
    packet.add_byte(agility)
    packet.add_byte(intelligence)
    packet.add_byte(charisma)
    packet.add_byte(constitution)
    return packet.to_bytes()
