"""Tests para msg_map.py."""

from src.msg_map import (
    build_block_position_response,
    build_change_map_response,
    build_object_create_response,
    build_object_delete_response,
    build_pos_update_response,
)
from src.packet_id import ServerPacketID


def test_build_change_map_response() -> None:
    """Verifica que build_change_map_response construye el paquete correctamente."""
    response = build_change_map_response(map_number=5, version=1)

    assert isinstance(response, bytes)
    assert len(response) == 5  # 1 byte PacketID + 2 bytes map + 2 bytes version
    assert response[0] == ServerPacketID.CHANGE_MAP


def test_build_pos_update_response() -> None:
    """Verifica que build_pos_update_response construye el paquete correctamente."""
    response = build_pos_update_response(x=50, y=47)

    assert isinstance(response, bytes)
    assert len(response) == 3  # 1 byte PacketID + 1 byte x + 1 byte y
    assert response[0] == ServerPacketID.POS_UPDATE
    assert response[1] == 50
    assert response[2] == 47


def test_build_object_create_response() -> None:
    """Verifica que build_object_create_response construye el paquete correctamente."""
    response = build_object_create_response(x=10, y=20, grh_index=1234)

    assert isinstance(response, bytes)
    assert len(response) == 5  # 1 byte PacketID + 1 byte x + 1 byte y + 2 bytes grh
    assert response[0] == ServerPacketID.OBJECT_CREATE
    assert response[1] == 10
    assert response[2] == 20


def test_build_block_position_response_blocked() -> None:
    """Verifica que build_block_position_response construye el paquete para tile bloqueado."""
    response = build_block_position_response(x=15, y=25, blocked=True)

    assert isinstance(response, bytes)
    assert len(response) == 4  # 1 byte PacketID + 1 byte x + 1 byte y + 1 byte blocked
    assert response[0] == ServerPacketID.BLOCK_POSITION
    assert response[1] == 15
    assert response[2] == 25
    assert response[3] == 1  # blocked = True


def test_build_block_position_response_unblocked() -> None:
    """Verifica que build_block_position_response construye el paquete para tile desbloqueado."""
    response = build_block_position_response(x=15, y=25, blocked=False)

    assert isinstance(response, bytes)
    assert response[3] == 0  # blocked = False


def test_build_object_delete_response() -> None:
    """Verifica que build_object_delete_response construye el paquete correctamente."""
    response = build_object_delete_response(x=30, y=40)

    assert isinstance(response, bytes)
    assert len(response) == 3  # 1 byte PacketID + 1 byte x + 1 byte y
    assert response[0] == ServerPacketID.OBJECT_DELETE
    assert response[1] == 30
    assert response[2] == 40
