"""Tests para msg_character.py."""

from src.network.msg_character import (
    build_character_change_response,
    build_character_create_response,
    build_character_move_response,
    build_character_remove_response,
)
from src.network.packet_id import ServerPacketID


def test_build_character_remove_response() -> None:
    """Verifica que build_character_remove_response construye el paquete correctamente."""
    response = build_character_remove_response(char_index=100)

    assert isinstance(response, bytes)
    assert len(response) == 3  # 1 byte PacketID + 2 bytes int16
    assert response[0] == ServerPacketID.CHARACTER_REMOVE


def test_build_character_change_response() -> None:
    """Verifica que build_character_change_response construye el paquete correctamente."""
    response = build_character_change_response(
        char_index=50, body=1, head=2, heading=3, weapon=10, shield=20, helmet=30, fx=5, loops=3
    )

    assert isinstance(response, bytes)
    assert response[0] == ServerPacketID.CHARACTER_CHANGE


def test_build_character_create_response() -> None:
    """Verifica que build_character_create_response construye el paquete correctamente."""
    response = build_character_create_response(
        char_index=1,
        body=1,
        head=1,
        heading=1,
        x=50,
        y=50,
        name="TestPlayer",
        nick_color=5,
        privileges=0,
    )

    assert isinstance(response, bytes)
    assert response[0] == ServerPacketID.CHARACTER_CREATE


def test_build_character_move_response() -> None:
    """Verifica que build_character_move_response construye el paquete correctamente."""
    response = build_character_move_response(char_index=10, x=55, y=60)

    assert isinstance(response, bytes)
    assert len(response) == 5  # 1 byte PacketID + 2 bytes char_index + 1 byte x + 1 byte y
    assert response[0] == ServerPacketID.CHARACTER_MOVE
