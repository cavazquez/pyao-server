"""Tests unitarios para NpcIndex (NPCs por mapa y ocupación de tiles)."""

from types import SimpleNamespace
from typing import TYPE_CHECKING, cast

import pytest

from src.game.npc_index import NpcIndex

if TYPE_CHECKING:
    from src.models.npc import NPC


def make_npc(
    *,
    x: int = 1,
    y: int = 1,
    instance_id: str = "npc-1",
    char_index: int = 1,
    name: str = "NPC",
) -> SimpleNamespace:
    """Crea un NPC liviano para pruebas."""
    return SimpleNamespace(x=x, y=y, instance_id=instance_id, char_index=char_index, name=name)


def test_add_npc_marks_occupation_and_storage() -> None:
    """Agrega un NPC y marca ocupación."""
    tile_occupation: dict[tuple[int, int, int], str] = {}
    index = NpcIndex(tile_occupation)
    npc = make_npc()

    index.add_npc(1, cast("NPC", npc))

    assert tile_occupation[1, 1, 1] == "npc:npc-1"
    assert index.get_npcs_in_map(1)[0] is npc


def test_add_npc_conflict_raises_value_error() -> None:
    """Falla si el tile ya está ocupado."""
    tile_occupation: dict[tuple[int, int, int], str] = {(1, 1, 1): "player:99"}
    index = NpcIndex(tile_occupation)

    with pytest.raises(ValueError, match="tile ya ocupado"):
        index.add_npc(1, cast("NPC", make_npc()))


def test_move_npc_updates_tile_occupation() -> None:
    """Mover un NPC libera y reasigna ocupación."""
    tile_occupation: dict[tuple[int, int, int], str] = {}
    index = NpcIndex(tile_occupation)
    npc = make_npc(char_index=5)
    index.add_npc(1, cast("NPC", npc))

    index.move_npc(1, 5, old_x=1, old_y=1, new_x=2, new_y=3)

    assert (1, 1, 1) not in tile_occupation
    assert tile_occupation[1, 2, 3] == "npc:npc-1"


def test_remove_npc_clears_tile_and_map() -> None:
    """Al remover un NPC se libera tile y mapa vacío se elimina."""
    tile_occupation: dict[tuple[int, int, int], str] = {}
    index = NpcIndex(tile_occupation)
    npc = make_npc()
    index.add_npc(1, cast("NPC", npc))

    index.remove_npc(1, "npc-1")

    assert (1, 1, 1) not in tile_occupation
    assert index.get_npcs_in_map(1) == []


def test_get_all_and_by_char_index() -> None:
    """Listar todos y buscar por char_index."""
    tile_occupation: dict[tuple[int, int, int], str] = {}
    index = NpcIndex(tile_occupation)
    npc1 = make_npc(instance_id="npc-1", char_index=10)
    npc2 = make_npc(instance_id="npc-2", char_index=20, x=5, y=5)

    index.add_npc(1, cast("NPC", npc1))
    index.add_npc(2, cast("NPC", npc2))

    all_npcs = index.get_all_npcs()
    assert len(all_npcs) == 2
    assert npc1 in all_npcs
    assert npc2 in all_npcs
    assert index.get_npc_by_char_index(1, 10) is npc1
    assert index.get_npc_by_char_index(2, 20) is npc2
    assert index.get_npc_by_char_index(1, 999) is None
