"""Tests para TileOccupation."""

import pytest

from src.game.tile_occupation import TileOccupation


def test_occupy_npc_conflict() -> None:
    """Occupy NPC falla en conflicto."""
    occ = TileOccupation()
    occ.occupy_npc(1, 1, 1, "npc-1")

    with pytest.raises(ValueError, match="ocupado"):
        occ.occupy_npc(1, 1, 1, "npc-2")


def test_move_and_remove_player() -> None:
    """Mueve y libera jugador."""
    occ = TileOccupation()
    occ.occupy_player(1, 5, 5, 10)
    assert occ.is_occupied(1, 5, 5)

    occ.move_player(1, 5, 5, 6, 7, 10)
    assert not occ.is_occupied(1, 5, 5)
    assert occ.get_occupant(1, 6, 7) == "player:10"

    occ.remove_player(10, map_id=1)
    assert not occ.is_occupied(1, 6, 7)


def test_remove_npc_by_instance() -> None:
    """Remueve NPC por instancia."""
    occ = TileOccupation()
    occ.occupy_npc(1, 2, 2, "npc-1")
    occ.remove_npc_by_instance("npc-1", map_id=1)
    assert not occ.is_occupied(1, 2, 2)
