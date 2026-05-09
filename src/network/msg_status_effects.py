"""Construcción de mensajes de efectos de estado (ceguera, estupidez, invisibilidad, etc.)."""

from src.network.packet_builder import PacketBuilder
from src.network.packet_id import ServerPacketID


def build_blind_response() -> bytes:
    """Construye el paquete BLIND del protocolo AO estándar.

    Activa el efecto visual de ceguera en el cliente.
    El cliente establece userCiego = true.

    Returns:
        Paquete de bytes: PacketID (56).
    """
    return bytes([ServerPacketID.BLIND])


def build_blind_no_more_response() -> bytes:
    """Construye el paquete BLIND_NO_MORE del protocolo AO estándar.

    Desactiva el efecto de ceguera en el cliente.
    El cliente establece userCiego = false.

    Returns:
        Paquete de bytes: PacketID (69).
    """
    return bytes([ServerPacketID.BLIND_NO_MORE])


def build_dumb_response() -> bytes:
    """Construye el paquete DUMB del protocolo AO estándar.

    Activa el efecto de estupidez en el cliente (no puede lanzar hechizos).
    El cliente establece userEstupido = true.

    Returns:
        Paquete de bytes: PacketID (57).
    """
    return bytes([ServerPacketID.DUMB])


def build_dumb_no_more_response() -> bytes:
    """Construye el paquete DUMB_NO_MORE del protocolo AO estándar.

    Desactiva el efecto de estupidez en el cliente.
    El cliente establece userEstupido = false.

    Returns:
        Paquete de bytes: PacketID (70).
    """
    return bytes([ServerPacketID.DUMB_NO_MORE])


def build_paralize_ok_response() -> bytes:
    """Construye el paquete PARALIZE_OK del protocolo AO estándar.

    Confirma la parálisis/inmovilización al cliente.
    El cliente alterna userParalizado.

    Returns:
        Paquete de bytes: PacketID (82).
    """
    return bytes([ServerPacketID.PARALIZE_OK])


def build_rest_ok_response() -> bytes:
    """Construye el paquete REST_OK del protocolo AO estándar.

    Confirma que el jugador puede descansar.
    El cliente alterna userDescansar.

    Returns:
        Paquete de bytes: PacketID (54).
    """
    return bytes([ServerPacketID.REST_OK])


def build_set_invisible_response(char_index: int, invisible: bool) -> bytes:
    """Construye el paquete SET_INVISIBLE del protocolo AO estándar.

    Marca un personaje como invisible o visible para el jugador.
    El cliente muestra/oculta el personaje según el flag.

    Args:
        char_index: Índice del personaje (int16).
        invisible: True para hacer visible (el cliente invierte la lógica).

    Returns:
        Paquete de bytes: PacketID (66) + charIndex (int16) + invisible (u8).
    """
    packet = PacketBuilder()
    packet.add_byte(ServerPacketID.SET_INVISIBLE)
    packet.add_int16(char_index)
    packet.add_byte(1 if invisible else 0)
    return packet.to_bytes()


def build_update_tag_and_status_response(
    char_index: int, nick_color: int, user_tag: str
) -> bytes:
    """Construye el paquete UPDATE_TAG_AND_STATUS del protocolo AO estándar.

     Actualiza el color del nick y el tag/nombre visible de un personaje.

    Args:
        char_index: Índice del personaje (int16).
        nick_color: Color del nick (u8). 0=Ciudadano, 1=Criminal, 2=Newbie, etc.
        user_tag: Nombre/tag del personaje (unicode string).

    Returns:
        Paquete de bytes: PacketID (89) + charIndex (int16) + nickColor (u8) + userTag (unicode).
    """
    packet = PacketBuilder()
    packet.add_byte(ServerPacketID.UPDATE_TAG_AND_STATUS)
    packet.add_int16(char_index)
    packet.add_byte(nick_color)
    packet.add_unicode_string(user_tag)
    return packet.to_bytes()
