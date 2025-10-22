"""Construcción de mensajes de consola."""

from src.network.packet_builder import PacketBuilder
from src.network.packet_id import ServerPacketID


def build_console_msg_response(message: str, font_color: int = 7) -> bytes:
    """Construye el paquete ConsoleMsg del protocolo AO estándar.

    Args:
        message: Mensaje a enviar.
        font_color: Color de la fuente (byte), por defecto 7 (blanco).

    Returns:
        Paquete de bytes con el formato: PacketID (24) + longitud (int16) + mensaje + color.
    """
    packet = PacketBuilder()
    packet.add_byte(ServerPacketID.CONSOLE_MSG)
    packet.add_unicode_string(message)
    packet.add_byte(font_color)
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
    packet.add_unicode_string(error_message)
    return packet.to_bytes()
