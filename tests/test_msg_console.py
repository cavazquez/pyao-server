"""Tests para msg_console.py."""

from src.msg_console import build_console_msg_response, build_error_msg_response
from src.packet_id import ServerPacketID


def test_build_console_msg_response() -> None:
    """Verifica que build_console_msg_response construye el paquete correctamente."""
    response = build_console_msg_response("Hola mundo", font_color=5)

    assert isinstance(response, bytes)
    assert response[0] == ServerPacketID.CONSOLE_MSG
    # Último byte debe ser el color
    assert response[-1] == 5


def test_build_console_msg_response_default_color() -> None:
    """Verifica que build_console_msg_response usa color por defecto."""
    response = build_console_msg_response("Test")

    assert isinstance(response, bytes)
    assert response[-1] == 7  # Color por defecto


def test_build_error_msg_response() -> None:
    """Verifica que build_error_msg_response construye el paquete correctamente."""
    response = build_error_msg_response("Error de prueba")

    assert isinstance(response, bytes)
    assert response[0] == ServerPacketID.ERROR_MSG
