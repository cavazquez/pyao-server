"""Tests para ExitIndex."""

from src.game.exit_index import ExitIndex


def test_exit_index_get_and_update() -> None:
    """Actualiza y consulta exits."""
    index = ExitIndex()
    exits = {(1, 10, 20): {"to_map": 2, "to_x": 5, "to_y": 6}}
    index.update(exits)

    assert index.get_exit_tile(1, 10, 20) == {"to_map": 2, "to_x": 5, "to_y": 6}
    assert index.get_exit_tile(1, 1, 1) is None
    assert index.get_map_ids() == {1}


def test_exit_index_clear_map() -> None:
    """Limpia exits de un mapa."""
    index = ExitIndex()
    index.update(
        {
            (1, 1, 1): {"to_map": 2, "to_x": 1, "to_y": 1},
            (2, 1, 1): {"to_map": 3, "to_x": 1, "to_y": 1},
        }
    )

    index.clear_map(1)

    assert index.get_exit_tile(1, 1, 1) is None
    assert index.get_exit_tile(2, 1, 1) is not None
