"""Construcción de mensajes de personajes."""

from src.packet_builder import PacketBuilder
from src.packet_id import ServerPacketID


def build_character_remove_response(char_index: int) -> bytes:
    """Construye el paquete CharacterRemove del protocolo AO estándar.

    Args:
        char_index: Índice del personaje a remover (int16).

    Returns:
        Paquete de bytes con el formato: PacketID (30) + char_index.
    """
    packet = PacketBuilder()
    packet.add_byte(ServerPacketID.CHARACTER_REMOVE)
    packet.add_int16(char_index)
    return packet.to_bytes()


def build_character_change_response(
    char_index: int,
    body: int,
    head: int,
    heading: int,
    weapon: int = 0,
    shield: int = 0,
    helmet: int = 0,
    fx: int = 0,
    loops: int = 0,
) -> bytes:
    """Construye el paquete CharacterChange del protocolo AO estándar.

    Args:
        char_index: Índice del personaje (int16).
        body: ID del cuerpo (int16).
        head: ID de la cabeza (int16).
        heading: Dirección (1=Norte, 2=Este, 3=Sur, 4=Oeste) (byte).
        weapon: ID del arma equipada (int16).
        shield: ID del escudo equipado (int16).
        helmet: ID del casco equipado (int16).
        fx: ID del efecto visual (int16).
        loops: Número de loops del efecto (int16).

    Returns:
        Paquete de bytes con el formato: PacketID (34) + datos del personaje.
    """
    packet = PacketBuilder()
    packet.add_byte(ServerPacketID.CHARACTER_CHANGE)
    packet.add_int16(char_index)
    packet.add_int16(body)
    packet.add_int16(head)
    packet.add_byte(heading)
    packet.add_int16(weapon)
    packet.add_int16(shield)
    packet.add_int16(helmet)
    packet.add_int16(fx)
    packet.add_int16(loops)
    return packet.to_bytes()


def build_character_create_response(
    char_index: int,
    body: int,
    head: int,
    heading: int,
    x: int,
    y: int,
    weapon: int = 0,
    shield: int = 0,
    helmet: int = 0,
    fx: int = 0,
    loops: int = 0,
    name: str = "",
    nick_color: int = 0,
    privileges: int = 0,
) -> bytes:
    """Construye el paquete CharacterCreate del protocolo AO estándar.

    Args:
        char_index: Índice del personaje (int16).
        body: ID del cuerpo/raza (int16).
        head: ID de la cabeza (int16).
        heading: Dirección que mira el personaje (byte: 1=Norte, 2=Este, 3=Sur, 4=Oeste).
        x: Posición X (byte).
        y: Posición Y (byte).
        weapon: ID del arma equipada (int16), por defecto 0.
        shield: ID del escudo equipado (int16), por defecto 0.
        helmet: ID del casco equipado (int16), por defecto 0.
        fx: ID del efecto visual (int16), por defecto 0.
        loops: Loops del efecto (int16), por defecto 0.
        name: Nombre del personaje (string), por defecto vacío.
        nick_color: Color del nick (byte), por defecto 0.
        privileges: Privilegios del personaje (byte), por defecto 0.

    Returns:
        Paquete de bytes con el formato CHARACTER_CREATE.
    """
    packet = PacketBuilder()
    packet.add_byte(ServerPacketID.CHARACTER_CREATE)
    packet.add_int16(char_index)
    packet.add_int16(body)
    packet.add_int16(head)
    packet.add_byte(heading)
    packet.add_byte(x)
    packet.add_byte(y)
    packet.add_int16(weapon)
    packet.add_int16(shield)
    packet.add_int16(helmet)
    packet.add_int16(fx)
    packet.add_int16(loops)
    # Agregar nombre con longitud en bytes UTF-8
    packet.add_unicode_string(name)
    packet.add_byte(nick_color)
    packet.add_byte(privileges)
    return packet.to_bytes()


def build_character_move_response(char_index: int, x: int, y: int) -> bytes:
    """Construye el paquete CHARACTER_MOVE para notificar movimiento de un personaje.

    Args:
        char_index: Índice del personaje que se mueve.
        x: Nueva posición X.
        y: Nueva posición Y.

    Returns:
        Paquete de bytes con el formato: PacketID + CharIndex + X + Y.
        NOTA: Heading NO se envía porque el cliente Godot no lo lee.
    """
    packet = PacketBuilder()
    packet.add_byte(ServerPacketID.CHARACTER_MOVE)
    packet.add_int16(char_index)
    packet.add_byte(x)
    packet.add_byte(y)
    return packet.to_bytes()
