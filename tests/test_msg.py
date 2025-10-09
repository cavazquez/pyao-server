"""Tests para el módulo de construcción de mensajes."""

import pytest

from src.msg import build_dice_roll_response
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
