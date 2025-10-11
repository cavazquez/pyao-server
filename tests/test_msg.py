"""Tests para el módulo de construcción de mensajes."""

import pytest

from src.msg import (
    build_account_created_response,
    build_account_error_response,
    build_dice_roll_response,
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


def test_build_account_created_response_structure() -> None:
    """Verifica que el paquete de cuenta creada tenga la estructura correcta."""
    user_id = 100
    response = build_account_created_response(user_id)

    # Verificar longitud: 1 byte PacketID + 4 bytes int32
    assert len(response) == 5

    # Verificar PacketID
    assert response[0] == ServerPacketID.ACCOUNT_CREATED


def test_build_account_created_response_user_id() -> None:
    """Verifica que el user_id se codifique correctamente."""
    user_id = 12345
    response = build_account_created_response(user_id)

    # Decodificar user_id (int32 little-endian)
    decoded_id = int.from_bytes(response[1:5], byteorder="little", signed=True)
    assert decoded_id == user_id


def test_build_account_created_response_large_user_id() -> None:
    """Verifica con user_id grande."""
    user_id = 999999
    response = build_account_created_response(user_id)

    decoded_id = int.from_bytes(response[1:5], byteorder="little", signed=True)
    assert decoded_id == user_id


def test_build_account_error_response_structure() -> None:
    """Verifica que el paquete de error tenga la estructura correcta."""
    error_msg = "Error de prueba"
    response = build_account_error_response(error_msg)

    # Verificar PacketID
    assert response[0] == ServerPacketID.ACCOUNT_ERROR

    # Verificar longitud del mensaje (int16, little-endian)
    msg_length = int.from_bytes(response[1:3], byteorder="little", signed=True)
    assert msg_length == len(error_msg.encode("utf-8"))

    # Verificar mensaje
    decoded_msg = response[3 : 3 + msg_length].decode("utf-8")
    assert decoded_msg == error_msg


def test_build_account_error_response_empty() -> None:
    """Verifica con mensaje vacío."""
    response = build_account_error_response("")

    assert response[0] == ServerPacketID.ACCOUNT_ERROR
    # PacketID (1 byte) + length (2 bytes) = 3 bytes total
    assert len(response) == 3
    msg_length = int.from_bytes(response[1:3], byteorder="little", signed=True)
    assert msg_length == 0


def test_build_account_error_response_long_message() -> None:
    """Verifica con mensaje largo."""
    error_msg = "Este es un mensaje de error muy largo " * 10
    response = build_account_error_response(error_msg)

    assert response[0] == ServerPacketID.ACCOUNT_ERROR
    msg_length = int.from_bytes(response[1:3], byteorder="little", signed=True)
    decoded_msg = response[3 : 3 + msg_length].decode("utf-8")
    assert decoded_msg == error_msg
