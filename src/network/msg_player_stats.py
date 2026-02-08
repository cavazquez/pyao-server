"""Construcción de mensajes de stats del jugador."""

from src.network.packet_builder import PacketBuilder
from src.network.packet_id import ServerPacketID


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


def build_update_exp_response(experience: int) -> bytes:
    """Construye el paquete UpdateExp del protocolo AO estándar.

    Args:
        experience: Puntos de experiencia actuales (int32).

    Returns:
        Paquete de bytes con el formato: PacketID (20) + experience (int32).
    """
    packet = PacketBuilder()
    packet.add_byte(ServerPacketID.UPDATE_EXP)
    packet.add_int32(experience)
    return packet.to_bytes()


def build_update_gold_response(gold: int) -> bytes:
    """Construye el paquete UpdateGold del protocolo AO estándar.

    Args:
        gold: Cantidad total de oro del jugador (int32).

    Returns:
        Paquete de bytes con el formato: PacketID (18) + gold (int32).
    """
    packet = PacketBuilder()
    packet.add_byte(ServerPacketID.UPDATE_GOLD)
    packet.add_int32(gold)
    return packet.to_bytes()


def build_update_bank_gold_response(bank_gold: int) -> bytes:
    """Construye el paquete UpdateBankGold del protocolo AO estándar.

    Args:
        bank_gold: Cantidad de oro en el banco (int32).

    Returns:
        Paquete de bytes con el formato: PacketID (19) + bank_gold (int32).
    """
    packet = PacketBuilder()
    packet.add_byte(ServerPacketID.UPDATE_BANK_GOLD)
    packet.add_int32(bank_gold)
    return packet.to_bytes()


def build_update_hunger_and_thirst_response(
    max_water: int, min_water: int, max_hunger: int, min_hunger: int
) -> bytes:
    """Construye el paquete UpdateHungerAndThirst del protocolo AO estándar.

    Args:
        max_water: Sed máxima (u8).
        min_water: Sed actual (u8).
        max_hunger: Hambre máxima (u8).
        min_hunger: Hambre actual (u8).

    Returns:
        Paquete de bytes con el formato: PacketID (60) + maxAgua + minAgua + maxHam + minHam.
    """
    packet = PacketBuilder()
    packet.add_byte(ServerPacketID.UPDATE_HUNGER_AND_THIRST)
    packet.add_byte(max_water)
    packet.add_byte(min_water)
    packet.add_byte(max_hunger)
    packet.add_byte(min_hunger)
    return packet.to_bytes()


def build_update_strength_and_dexterity_response(strength: int, dexterity: int) -> bytes:
    """Construye el paquete UpdateStrengthAndDexterity (PacketID 100).

    Args:
        strength: Valor actual de fuerza (u8).
        dexterity: Valor actual de agilidad (u8).

    Returns:
        Paquete de bytes con el formato: PacketID (100) + fuerza + agilidad.
    """
    packet = PacketBuilder()
    packet.add_byte(ServerPacketID.UPDATE_STRENGTH_AND_DEXTERITY)
    packet.add_byte(strength)
    packet.add_byte(dexterity)
    return packet.to_bytes()


def build_update_strength_response(strength: int) -> bytes:
    """Construye el paquete UpdateStrength (PacketID 101).

    Args:
        strength: Valor actual de fuerza (u8).

    Returns:
        bytes: Paquete con el formato PacketID (101) + fuerza.
    """
    packet = PacketBuilder()
    packet.add_byte(ServerPacketID.UPDATE_STRENGTH)
    packet.add_byte(strength)
    return packet.to_bytes()


def build_update_dexterity_response(dexterity: int) -> bytes:
    """Construye el paquete UpdateDexterity (PacketID 102).

    Args:
        dexterity: Valor actual de agilidad (u8).

    Returns:
        bytes: Paquete con el formato PacketID (102) + agilidad.
    """
    packet = PacketBuilder()
    packet.add_byte(ServerPacketID.UPDATE_DEXTERITY)
    packet.add_byte(dexterity)
    return packet.to_bytes()


def build_update_user_stats_response(
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
        Orden: min/max (actual/máximo) para cada stat.
    """
    # Clamp valores a int16 para evitar overflow (-32768 a 32767)
    max_int16 = 32767
    min_int16 = -32768

    packet = PacketBuilder()
    packet.add_byte(ServerPacketID.UPDATE_USER_STATS)
    # Orden según cliente Godot: max/min (máximo/actual)
    packet.add_int16(max(min(max_hp, max_int16), min_int16))
    packet.add_int16(max(min(min_hp, max_int16), min_int16))
    packet.add_int16(max(min(max_mana, max_int16), min_int16))
    packet.add_int16(max(min(min_mana, max_int16), min_int16))
    packet.add_int16(max(min(max_sta, max_int16), min_int16))
    packet.add_int16(max(min(min_sta, max_int16), min_int16))
    packet.add_int32(gold)
    packet.add_byte(level)
    packet.add_int32(elu)
    packet.add_int32(experience)
    return packet.to_bytes()
