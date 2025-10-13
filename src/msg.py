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


def build_update_hp_response(hp: int) -> bytes:
    """Construye el paquete UpdateHP del protocolo AO estándar.

    Args:
        hp: Puntos de vida actuales (int16).

    Returns:
        Paquete de bytes con el formato: PacketID (17) + hp (int16).
    """
    packet = PacketBuilder()
    packet.add_byte(ServerPacketID.UPDATE_HP)
    packet.add_int16(hp)
    return packet.to_bytes()


def build_update_mana_response(mana: int) -> bytes:
    """Construye el paquete UpdateMana del protocolo AO estándar.

    Args:
        mana: Puntos de mana actuales (int16).

    Returns:
        Paquete de bytes con el formato: PacketID (16) + mana (int16).
    """
    packet = PacketBuilder()
    packet.add_byte(ServerPacketID.UPDATE_MANA)
    packet.add_int16(mana)
    return packet.to_bytes()


def build_update_sta_response(stamina: int) -> bytes:
    """Construye el paquete UpdateSta del protocolo AO estándar.

    Args:
        stamina: Puntos de stamina actuales (int16).

    Returns:
        Paquete de bytes con el formato: PacketID (15) + stamina (int16).
    """
    packet = PacketBuilder()
    packet.add_byte(ServerPacketID.UPDATE_STA)
    packet.add_int16(stamina)
    return packet.to_bytes()


def build_update_user_stats_response(  # noqa: PLR0913, PLR0917
    max_hp: int,
    min_hp: int,
    max_mana: int,
    min_mana: int,
    max_sta: int,
    min_sta: int,
    gold: int,
    level: int,
    elu: int,
    experience: int,
) -> bytes:
    """Construye el paquete UpdateUserStats del protocolo AO estándar.

    Args:
        max_hp: HP máximo (int16).
        min_hp: HP actual (int16).
        max_mana: Mana máximo (int16).
        min_mana: Mana actual (int16).
        max_sta: Stamina máxima (int16).
        min_sta: Stamina actual (int16).
        gold: Oro del jugador (int32).
        level: Nivel del jugador (byte).
        elu: Experiencia para subir de nivel (int32).
        experience: Experiencia total (int32).

    Returns:
        Paquete de bytes con el formato: PacketID (45) + stats.
    """
    packet = PacketBuilder()
    packet.add_byte(ServerPacketID.UPDATE_USER_STATS)
    packet.add_int16(max_hp)
    packet.add_int16(min_hp)
    packet.add_int16(max_mana)
    packet.add_int16(min_mana)
    packet.add_int16(max_sta)
    packet.add_int16(min_sta)
    packet.add_int32(gold)
    packet.add_byte(level)
    packet.add_int32(elu)
    packet.add_int32(experience)
    return packet.to_bytes()
