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
    packet.add_unicode_string(error_message)
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
    packet = PacketBuilder()
    packet.add_byte(ServerPacketID.UPDATE_USER_STATS)
    # Orden según cliente Godot: max/min (máximo/actual)
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


def build_commerce_end_response() -> bytes:
    """Construye el paquete CommerceEnd del protocolo AO estándar.

    Returns:
        Paquete de bytes con el formato: PacketID (5).
    """
    packet = PacketBuilder()
    packet.add_byte(ServerPacketID.COMMERCE_END)
    return packet.to_bytes()


def build_play_midi_response(midi_id: int) -> bytes:
    """Construye el paquete PlayMIDI del protocolo AO estándar.

    Args:
        midi_id: ID de la música MIDI a reproducir (byte).

    Returns:
        Paquete de bytes con el formato: PacketID (38) + midi (1 byte).
    """
    packet = PacketBuilder()
    packet.add_byte(ServerPacketID.PLAY_MIDI)
    packet.add_byte(midi_id)
    return packet.to_bytes()


def build_play_wave_response(wave_id: int, x: int = 0, y: int = 0) -> bytes:
    """Construye el paquete PlayWave del protocolo AO estándar.

    Args:
        wave_id: ID del sonido a reproducir (byte).
        x: Posición X del sonido (byte), 0 para sonido global.
        y: Posición Y del sonido (byte), 0 para sonido global.

    Returns:
        Paquete de bytes con el formato: PacketID (39) + wave (1 byte) + x (1 byte) + y (1 byte).
    """
    packet = PacketBuilder()
    packet.add_byte(ServerPacketID.PLAY_WAVE)
    packet.add_byte(wave_id)
    packet.add_byte(x)
    packet.add_byte(y)
    return packet.to_bytes()


def build_create_fx_response(char_index: int, fx: int, loops: int) -> bytes:
    """Construye el paquete CreateFX del protocolo AO estándar.

    Args:
        char_index: ID del personaje/objeto que genera el efecto (int16).
        fx: ID del efecto visual (int16).
        loops: Número de loops (int16). -1 = infinito, 0 = una vez, >0 = número específico.

    Returns:
        Paquete de bytes: PacketID (44) + charIndex (int16) + fx (int16) + loops (int16).
    """
    packet = PacketBuilder()
    packet.add_byte(ServerPacketID.CREATE_FX)
    packet.add_int16(char_index)
    packet.add_int16(fx)
    packet.add_int16(loops)
    return packet.to_bytes()


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
    # Agregar mensaje con longitud en bytes UTF-8
    packet.add_unicode_string(message)
    # Agregar color
    packet.add_byte(font_color)
    return packet.to_bytes()


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


def build_change_inventory_slot_response(
    slot: int,
    item_id: int,
    name: str,
    amount: int,
    equipped: bool,
    grh_id: int,
    item_type: int,
    max_hit: int,
    min_hit: int,
    max_def: int,
    min_def: int,
    sale_price: float,
) -> bytes:
    """Construye el paquete para actualizar un slot del inventario.

    Args:
        slot: Número de slot (1-20).
        item_id: ID del item (index).
        name: Nombre del item.
        amount: Cantidad del item.
        equipped: Si está equipado (True/False).
        grh_id: ID del gráfico.
        item_type: Tipo de item.
        max_hit: Daño máximo.
        min_hit: Daño mínimo.
        max_def: Defensa máxima.
        min_def: Defensa mínima.
        sale_price: Precio de venta.

    Returns:
        Paquete de bytes con el formato del cliente.
    """
    packet = PacketBuilder()
    packet.add_byte(ServerPacketID.CHANGE_INVENTORY_SLOT)
    packet.add_byte(slot)
    packet.add_int16(item_id)
    packet.add_unicode_string(name)
    packet.add_int16(amount)
    packet.add_byte(1 if equipped else 0)
    packet.add_int16(grh_id)
    packet.add_byte(item_type)
    # Cliente espera: maxHit, minHit, maxDef, minDef
    packet.add_int16(max_hit)
    packet.add_int16(min_hit)
    packet.add_int16(max_def)
    packet.add_int16(min_def)
    packet.add_float(sale_price)
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
        Paquete de bytes con el formato: PacketID (36) + X + Y.
    """
    packet = PacketBuilder()
    packet.add_byte(ServerPacketID.OBJECT_DELETE)
    packet.add_byte(x)
    packet.add_byte(y)
    return packet.to_bytes()
