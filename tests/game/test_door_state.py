"""Tests para DoorState."""

from src.game.door_state import DoorState


def test_block_and_unblock() -> None:
    """Cerrar y abrir puerta."""
    state = DoorState()
    state.block(1, 2, 3)

    assert state.is_closed(1, 2, 3)
    state.unblock(1, 2, 3)
    assert not state.is_closed(1, 2, 3)


def test_clear_map() -> None:
    """Limpiar puertas de un mapa."""
    state = DoorState()
    state.block(1, 1, 1)
    state.block(2, 2, 2)

    state.clear_map(1)

    assert not state.is_closed(1, 1, 1)
    assert state.is_closed(2, 2, 2)
