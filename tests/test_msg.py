"""Tests para el módulo de construcción de mensajes."""

import pytest

from src.msg import (
    build_change_map_response,
    build_character_change_response,
    build_character_create_response,
    build_dice_roll_response,
    build_error_msg_response,
    build_logged_response,
    build_user_char_index_in_server_response,
)
from src.packet_id import ServerPacketID


def test_build_dice_roll_response_structure() -> None:
    """Verifica que el paquete tenga la estructura correcta."""
    response = build_dice_roll_response(
        strength=10,
        agility=12,
        intelligence=14,
        charisma=16,
        constitution=18,
    )

    # Verificar longitud: 1 byte de PacketID + 5 bytes de atributos
    assert len(response) == 6

    # Verificar que el primer byte sea el PacketID correcto
    assert response[0] == ServerPacketID.DICE_ROLL


def test_build_dice_roll_response_values() -> None:
    """Verifica que los valores de atributos se incluyan correctamente."""
    strength = 15
    agility = 13
    intelligence = 11
    charisma = 9
    constitution = 17

    response = build_dice_roll_response(
        strength=strength,
        agility=agility,
        intelligence=intelligence,
        charisma=charisma,
        constitution=constitution,
    )

    # Verificar que cada atributo esté en su posición correcta
    assert response[1] == strength
    assert response[2] == agility
    assert response[3] == intelligence
    assert response[4] == charisma
    assert response[5] == constitution


def test_build_dice_roll_response_min_values() -> None:
    """Verifica que funcione con valores mínimos (6)."""
    response = build_dice_roll_response(
        strength=6,
        agility=6,
        intelligence=6,
        charisma=6,
        constitution=6,
    )

    assert len(response) == 6
    assert response[0] == ServerPacketID.DICE_ROLL
    assert all(response[i] == 6 for i in range(1, 6))


def test_build_dice_roll_response_max_values() -> None:
    """Verifica que funcione con valores máximos (18)."""
    response = build_dice_roll_response(
        strength=18,
        agility=18,
        intelligence=18,
        charisma=18,
        constitution=18,
    )

    assert len(response) == 6
    assert response[0] == ServerPacketID.DICE_ROLL
    assert all(response[i] == 18 for i in range(1, 6))


def test_build_dice_roll_response_mixed_values() -> None:
    """Verifica con una mezcla de valores bajos, medios y altos."""
    response = build_dice_roll_response(
        strength=6,
        agility=12,
        intelligence=18,
        charisma=9,
        constitution=15,
    )

    assert response[0] == ServerPacketID.DICE_ROLL
    assert response[1] == 6
    assert response[2] == 12
    assert response[3] == 18
    assert response[4] == 9
    assert response[5] == 15


def test_build_dice_roll_response_returns_bytes() -> None:
    """Verifica que el retorno sea de tipo bytes."""
    response = build_dice_roll_response(
        strength=10,
        agility=10,
        intelligence=10,
        charisma=10,
        constitution=10,
    )

    assert isinstance(response, bytes)


@pytest.mark.parametrize(
    ("strength", "agility", "intelligence", "charisma", "constitution"),
    [
        (6, 7, 8, 9, 10),
        (18, 17, 16, 15, 14),
        (10, 10, 10, 10, 10),
        (6, 18, 6, 18, 12),
    ],
)
def test_build_dice_roll_response_parametrized(
    strength: int,
    agility: int,
    intelligence: int,
    charisma: int,
    constitution: int,
) -> None:
    """Test parametrizado con diferentes combinaciones de valores."""
    response = build_dice_roll_response(
        strength=strength,
        agility=agility,
        intelligence=intelligence,
        charisma=charisma,
        constitution=constitution,
    )

    assert len(response) == 6
    assert response[0] == ServerPacketID.DICE_ROLL
    assert response[1] == strength
    assert response[2] == agility
    assert response[3] == intelligence
    assert response[4] == charisma
    assert response[5] == constitution


def test_build_logged_response_structure() -> None:
    """Verifica que el paquete Logged tenga la estructura correcta."""
    user_class = 1
    response = build_logged_response(user_class)

    # Verificar longitud: 1 byte PacketID + 1 byte userClass
    assert len(response) == 2

    # Verificar PacketID
    assert response[0] == ServerPacketID.LOGGED

    # Verificar userClass
    assert response[1] == user_class


def test_build_error_msg_response_structure() -> None:
    """Verifica que el paquete ErrorMsg tenga la estructura correcta."""
    error_msg = "Error de prueba"
    response = build_error_msg_response(error_msg)

    # Verificar PacketID
    assert response[0] == ServerPacketID.ERROR_MSG

    # Verificar longitud del mensaje (int16, little-endian)
    msg_length = int.from_bytes(response[1:3], byteorder="little", signed=True)
    assert msg_length == len(error_msg.encode("utf-8"))

    # Verificar mensaje
    decoded_msg = response[3 : 3 + msg_length].decode("utf-8")
    assert decoded_msg == error_msg


def test_build_error_msg_response_empty() -> None:
    """Verifica con mensaje vacío."""
    response = build_error_msg_response("")

    assert response[0] == ServerPacketID.ERROR_MSG
    # PacketID (1 byte) + length (2 bytes) = 3 bytes total
    assert len(response) == 3
    msg_length = int.from_bytes(response[1:3], byteorder="little", signed=True)
    assert msg_length == 0


def test_build_error_msg_response_long_message() -> None:
    """Verifica con mensaje largo."""
    error_msg = "Este es un mensaje de error muy largo " * 10
    response = build_error_msg_response(error_msg)

    assert response[0] == ServerPacketID.ERROR_MSG
    msg_length = int.from_bytes(response[1:3], byteorder="little", signed=True)
    decoded_msg = response[3 : 3 + msg_length].decode("utf-8")
    assert decoded_msg == error_msg


def test_build_user_char_index_in_server_response_structure() -> None:
    """Verifica que el paquete UserCharIndexInServer tenga la estructura correcta."""
    char_index = 42
    response = build_user_char_index_in_server_response(char_index)

    # Verificar longitud: 1 byte PacketID + 2 bytes int16
    assert len(response) == 3

    # Verificar PacketID
    assert response[0] == ServerPacketID.USER_CHAR_INDEX_IN_SERVER

    # Verificar charIndex (int16, little-endian)
    decoded_index = int.from_bytes(response[1:3], byteorder="little", signed=True)
    assert decoded_index == char_index


def test_build_user_char_index_in_server_response_values() -> None:
    """Verifica diferentes valores de charIndex."""
    test_values = [0, 1, 100, 1000, 32767]  # Valores válidos para int16

    for char_index in test_values:
        response = build_user_char_index_in_server_response(char_index)
        assert response[0] == ServerPacketID.USER_CHAR_INDEX_IN_SERVER
        decoded_index = int.from_bytes(response[1:3], byteorder="little", signed=True)
        assert decoded_index == char_index


def test_build_change_map_response_structure() -> None:
    """Verifica que el paquete ChangeMap tenga la estructura correcta."""
    map_number = 5
    version = 10
    response = build_change_map_response(map_number, version)

    # Verificar longitud: 1 byte PacketID + 2 bytes int16 (map) + 2 bytes int16 (version)
    assert len(response) == 5

    # Verificar PacketID
    assert response[0] == ServerPacketID.CHANGE_MAP

    # Verificar mapNumber (int16, little-endian)
    decoded_map = int.from_bytes(response[1:3], byteorder="little", signed=True)
    assert decoded_map == map_number

    # Verificar version (int16, little-endian)
    decoded_version = int.from_bytes(response[3:5], byteorder="little", signed=True)
    assert decoded_version == version


def test_build_change_map_response_values() -> None:
    """Verifica diferentes valores de mapNumber."""
    test_values = [1, 10, 100, 500, 1000]

    for map_number in test_values:
        response = build_change_map_response(map_number)
        assert response[0] == ServerPacketID.CHANGE_MAP
        decoded_map = int.from_bytes(response[1:3], byteorder="little", signed=True)
        assert decoded_map == map_number
        # Version por defecto debe ser 0
        decoded_version = int.from_bytes(response[3:5], byteorder="little", signed=True)
        assert decoded_version == 0


def test_build_character_create_response_structure() -> None:
    """Verifica que el paquete CharacterCreate tenga la estructura correcta."""
    response = build_character_create_response(
        char_index=100,
        body=1,
        head=5,
        heading=3,
        x=50,
        y=50,
        name="TestChar",
    )

    # Verificar que el primer byte sea el PacketID correcto
    assert response[0] == ServerPacketID.CHARACTER_CREATE

    # Verificar char_index (int16)
    char_index = int.from_bytes(response[1:3], byteorder="little", signed=True)
    assert char_index == 100

    # Verificar body (int16)
    body = int.from_bytes(response[3:5], byteorder="little", signed=True)
    assert body == 1

    # Verificar head (int16)
    head = int.from_bytes(response[5:7], byteorder="little", signed=True)
    assert head == 5

    # Verificar heading (byte)
    assert response[7] == 3

    # Verificar x (byte)
    assert response[8] == 50

    # Verificar y (byte)
    assert response[9] == 50


def test_build_character_create_response_with_equipment() -> None:
    """Verifica que el paquete incluya correctamente el equipamiento."""
    response = build_character_create_response(
        char_index=200,
        body=2,
        head=10,
        heading=1,
        x=100,
        y=100,
        weapon=15,
        shield=20,
        helmet=25,
        name="Warrior",
    )

    assert response[0] == ServerPacketID.CHARACTER_CREATE

    # Verificar weapon (int16) - offset 10
    weapon = int.from_bytes(response[10:12], byteorder="little", signed=True)
    assert weapon == 15

    # Verificar shield (int16) - offset 12
    shield = int.from_bytes(response[12:14], byteorder="little", signed=True)
    assert shield == 20

    # Verificar helmet (int16) - offset 14
    helmet = int.from_bytes(response[14:16], byteorder="little", signed=True)
    assert helmet == 25


def test_build_character_create_response_with_name() -> None:
    """Verifica que el nombre del personaje se incluya correctamente."""
    name = "TestPlayer"
    response = build_character_create_response(
        char_index=1,
        body=1,
        head=1,
        heading=1,
        x=1,
        y=1,
        name=name,
    )

    # Offset del nombre: PacketID(1) + char_index(2) + body(2) + head(2) +
    # heading(1) + x(1) + y(1) + weapon(2) + shield(2) + helmet(2) + fx(2) + loops(2) = 20 bytes
    # Luego viene: length(2) + string
    name_length_offset = 20
    name_length = int.from_bytes(
        response[name_length_offset : name_length_offset + 2], byteorder="little", signed=False
    )
    assert name_length == len(name)

    # Verificar el nombre
    name_start = name_length_offset + 2
    decoded_name = response[name_start : name_start + name_length].decode("utf-8")
    assert decoded_name == name


def test_build_character_change_response_structure() -> None:
    """Verifica que el paquete CHARACTER_CHANGE tenga la estructura correcta."""
    response = build_character_change_response(
        char_index=1,
        body=0,
        head=15,
        heading=3,
        weapon=0,
        shield=0,
        helmet=0,
        fx=0,
        loops=0,
    )

    # Verificar longitud: 1 byte PacketID + 2 charIndex + 2 body + 2 head + 1 heading
    # + 2 weapon + 2 shield + 2 helmet + 2 fx + 2 loops = 18 bytes
    assert len(response) == 18

    # Verificar PacketID
    assert response[0] == ServerPacketID.CHARACTER_CHANGE


def test_build_character_change_response_values() -> None:
    """Verifica que los valores se incluyan correctamente en CHARACTER_CHANGE."""
    char_index = 123
    body = 5
    head = 20
    heading = 4  # Oeste
    weapon = 10
    shield = 15
    helmet = 8
    fx = 2
    loops = 3

    response = build_character_change_response(
        char_index=char_index,
        body=body,
        head=head,
        heading=heading,
        weapon=weapon,
        shield=shield,
        helmet=helmet,
        fx=fx,
        loops=loops,
    )

    # Verificar charIndex (int16, little-endian)
    assert int.from_bytes(response[1:3], byteorder="little", signed=False) == char_index

    # Verificar body (int16)
    assert int.from_bytes(response[3:5], byteorder="little", signed=False) == body

    # Verificar head (int16)
    assert int.from_bytes(response[5:7], byteorder="little", signed=False) == head

    # Verificar heading (byte)
    assert response[7] == heading

    # Verificar weapon (int16)
    assert int.from_bytes(response[8:10], byteorder="little", signed=False) == weapon

    # Verificar shield (int16)
    assert int.from_bytes(response[10:12], byteorder="little", signed=False) == shield

    # Verificar helmet (int16)
    assert int.from_bytes(response[12:14], byteorder="little", signed=False) == helmet

    # Verificar fx (int16)
    assert int.from_bytes(response[14:16], byteorder="little", signed=False) == fx

    # Verificar loops (int16)
    assert int.from_bytes(response[16:18], byteorder="little", signed=False) == loops


def test_build_character_change_response_heading_directions() -> None:
    """Verifica que CHARACTER_CHANGE maneje todas las direcciones correctamente."""
    for heading in [1, 2, 3, 4]:  # Norte, Este, Sur, Oeste
        response = build_character_change_response(
            char_index=1,
            body=0,
            head=15,
            heading=heading,
        )

        # Verificar que el heading esté en la posición correcta
        assert response[7] == heading
