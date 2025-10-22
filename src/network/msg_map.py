"""Construcción de mensajes de mapa."""

from src.network.packet_builder import PacketBuilder
from src.network.packet_id import ServerPacketID


def build_change_map_response(map_number: int, version: int = 0) -> bytes:
    """Construye el paquete ChangeMap del protocolo AO estándar.

    Args:
        map_number: Número del mapa (int16).
        version: Versión del mapa (int16), por defecto 0.

    Returns:
        Paquete de bytes con el formato: PacketID (21) + mapNumber (int16) + version (int16).
    """
    packet = PacketBuilder()
    packet.add_byte(ServerPacketID.CHANGE_MAP)
    packet.add_int16(map_number)
    packet.add_int16(version)
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


def build_object_create_response(x: int, y: int, grh_index: int) -> bytes:
    """Construye el paquete ObjectCreate del protocolo AO estándar.

    Args:
        x: Posición X del objeto (byte).
        y: Posición Y del objeto (byte).
        grh_index: Índice gráfico del objeto (int16).

    Returns:
        Paquete de bytes con el formato: PacketID (35) + X + Y + GrhIndex.
    """
    packet = PacketBuilder()
    packet.add_byte(ServerPacketID.OBJECT_CREATE)
    packet.add_byte(x)
    packet.add_byte(y)
    packet.add_int16(grh_index)
    return packet.to_bytes()


def build_block_position_response(x: int, y: int, blocked: bool) -> bytes:
    """Construye el paquete BlockPosition del protocolo AO estándar.

    Args:
        x: Posición X (byte).
        y: Posición Y (byte).
        blocked: True si el tile está bloqueado, False si no (byte: 1 o 0).

    Returns:
        Paquete de bytes con el formato: PacketID (36) + X + Y + Blocked.
    """
    packet = PacketBuilder()
    packet.add_byte(ServerPacketID.BLOCK_POSITION)
    packet.add_byte(x)
    packet.add_byte(y)
    packet.add_byte(1 if blocked else 0)
    return packet.to_bytes()


def build_object_delete_response(x: int, y: int) -> bytes:
    """Construye el paquete ObjectDelete del protocolo AO estándar.

    Args:
        x: Posición X del objeto (byte).
        y: Posición Y del objeto (byte).

    Returns:
        Paquete de bytes con el formato: PacketID (37) + X + Y.
    """
    packet = PacketBuilder()
    packet.add_byte(ServerPacketID.OBJECT_DELETE)
    packet.add_byte(x)
    packet.add_byte(y)
    return packet.to_bytes()
