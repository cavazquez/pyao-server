"""Tests para msg_session.py."""

from src.msg_session import (
    build_attributes_response,
    build_dice_roll_response,
    build_logged_response,
    build_pong_response,
    build_user_char_index_in_server_response,
)
from src.packet_id import ServerPacketID


def test_build_dice_roll_response() -> None:
    """Verifica que build_dice_roll_response construye el paquete correctamente."""
    response = build_dice_roll_response(
        strength=15, agility=12, intelligence=14, charisma=10, constitution=13
    )

    assert isinstance(response, bytes)
    assert len(response) == 6  # 1 byte PacketID + 5 bytes atributos
    assert response[0] == ServerPacketID.DICE_ROLL
    assert response[1] == 15  # strength
    assert response[2] == 12  # agility
    assert response[3] == 14  # intelligence
    assert response[4] == 10  # charisma
    assert response[5] == 13  # constitution


def test_build_attributes_response() -> None:
    """Verifica que build_attributes_response construye el paquete correctamente."""
    response = build_attributes_response(
        strength=18, agility=16, intelligence=12, charisma=14, constitution=15
    )

    assert isinstance(response, bytes)
    assert len(response) == 6  # 1 byte PacketID + 5 bytes atributos
    assert response[0] == ServerPacketID.ATTRIBUTES
    assert response[1] == 18  # strength
    assert response[2] == 16  # agility
    assert response[3] == 12  # intelligence
    assert response[4] == 14  # charisma
    assert response[5] == 15  # constitution


def test_build_logged_response() -> None:
    """Verifica que build_logged_response construye el paquete correctamente."""
    response = build_logged_response(user_class=3)

    assert isinstance(response, bytes)
    assert len(response) == 2  # 1 byte PacketID + 1 byte user_class
    assert response[0] == ServerPacketID.LOGGED
    assert response[1] == 3


def test_build_user_char_index_in_server_response() -> None:
    """Verifica que build_user_char_index_in_server_response construye el paquete correctamente."""
    response = build_user_char_index_in_server_response(char_index=42)

    assert isinstance(response, bytes)
    assert len(response) == 3  # 1 byte PacketID + 2 bytes int16
    assert response[0] == ServerPacketID.USER_CHAR_INDEX_IN_SERVER
    # int16 little-endian: 42 = 0x002A = [0x2A, 0x00]
    assert response[1] == 42
    assert response[2] == 0


def test_build_pong_response() -> None:
    """Verifica que build_pong_response construye el paquete correctamente."""
    response = build_pong_response()

    assert isinstance(response, bytes)
    assert len(response) == 1
    assert response[0] == ServerPacketID.PONG
