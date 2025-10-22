"""Tests para msg_visual_effects.py."""

from src.network.msg_visual_effects import build_create_fx_response
from src.network.packet_id import ServerPacketID


def test_build_create_fx_response() -> None:
    """Verifica que build_create_fx_response construye el paquete correctamente."""
    response = build_create_fx_response(char_index=100, fx=5, loops=3)

    assert isinstance(response, bytes)
    assert len(response) == 7  # 1 byte PacketID + 3 * 2 bytes int16
    assert response[0] == ServerPacketID.CREATE_FX


def test_build_create_fx_response_infinite_loops() -> None:
    """Verifica que build_create_fx_response con loops infinitos."""
    response = build_create_fx_response(char_index=50, fx=10, loops=-1)

    assert isinstance(response, bytes)
    assert response[0] == ServerPacketID.CREATE_FX
