"""Los índices derivados conservan la identidad durante cambios de mapa y sesión."""

from unittest.mock import MagicMock

import pytest

from src.game.ground_item_index import GroundItemIndex
from src.game.npc_index import NpcIndex
from src.game.player_index import PlayerIndex
from src.game.tile_occupation import TileOccupation


def test_transition_removal_keeps_global_identity_until_last_map() -> None:
    """La retirada del mapa viejo no borra el índice de la sesión del nuevo."""
    index = PlayerIndex(TileOccupation())
    sender = MagicMock()
    index.add_player(1, 7, sender, "ÁLICE")
    index.add_player(2, 7, sender, "ÁLICE")
    index.remove_player(1, 7, expected_sender=sender)
    assert index.find_player_by_username("  álice  ") == 7
    assert index.get_message_sender(7) is sender
    index.remove_player(2, 7)
    assert index.find_player_by_username("Álice") is None
    assert index.get_message_sender(7) is None


def test_stale_session_cleanup_cannot_remove_reconnected_player() -> None:
    """Una conexión nueva reemplaza referencias viejas y admite limpieza tardía."""
    index = PlayerIndex(TileOccupation())
    old, new = MagicMock(), MagicMock()
    index.add_player(1, 7, old, "Alice")
    index.add_player(2, 7, new, "Alice")
    index.remove_player(1, 7, expected_sender=old)
    index.remove_player(2, 7, expected_sender=old)
    index.remove_player_from_all_maps(7, expected_sender=old)
    assert index.get_message_sender(7) is new
    assert index.get_players_in_map(1) == []
    assert index.get_players_in_map(2) == [7]
    index.remove_player_from_all_maps(7, expected_sender=new)
    index.remove_player_from_all_maps(7, expected_sender=new)
    assert index.get_message_sender(7) is None


def test_name_update_and_normalized_collision_do_not_leave_stale_aliases() -> None:
    """Conserva lower/strip y la búsqueda de otro usuario con el mismo nombre normalizado."""
    index = PlayerIndex(TileOccupation())
    sender = MagicMock()
    index.add_player(1, 1, sender, "A")
    index.add_player(1, 2, MagicMock(), "a")
    index.add_player(2, 1, sender, "B")
    assert index.find_player_by_username("a") == 2
    assert index.find_player_by_username(" b ") == 1
    assert index.get_username(1, 1) == "B"
    index.remove_player_from_all_maps(2)
    assert index.find_player_by_username("a") is None


def make_npc(identity: str, character: int, x: int = 1) -> MagicMock:
    """NPC liviano con identidad y posición mutables."""
    return MagicMock(
        instance_id=identity,
        char_index=character,
        x=x,
        y=1,
        name=identity,
        summoned_by_user_id=0,
        summoned_until=0,
        is_tamed=False,
    )


def test_npc_character_reuse_and_cross_map_rebinding() -> None:
    """El respawn y el traslado no encuentran la instancia retirada."""
    index = NpcIndex(TileOccupation())
    old = make_npc("old", 10001)
    index.add_npc(1, old)
    with pytest.raises(ValueError, match="CharIndex"):
        index.add_npc(1, make_npc("other", 10001, 2))
    index.remove_npc(1, "old")
    replacement = make_npc("new", 10001)
    index.add_npc(1, replacement)
    index.remove_npc(1, "old")
    assert index.get_npc_by_char_index(1, 10001) is replacement
    index.add_npc(2, replacement)
    assert index.get_npc_by_char_index(1, 10001) is None
    assert index.get_npc_by_char_index(2, 10001) is replacement
    index.move_npc(2, 10001, 1, 1, 3, 4)
    assert (replacement.x, replacement.y) == (3, 4)
    index.remove_npc(2, "new")
    assert index.get_all_npcs() == []


def test_ground_snapshot_and_replacement_do_not_scan_other_maps(monkeypatch) -> None:
    """Un bucket ajeno no se itera para consultar, reemplazar o limpiar un mapa."""
    index = GroundItemIndex(10)
    index.add_ground_item(1, 1, 1, {"item_id": 15, "quantity": 1})
    index.add_ground_item(2, 2, 2, {"item_id": 16, "quantity": 2})

    def forbidden_iteration(_self):
        message = "Se recorrió el mundo completo"
        raise AssertionError(message)

    monkeypatch.setattr(type(index.ground_items), "__iter__", forbidden_iteration)
    assert index.get_ground_items_count(1) == 1
    index._replace_map(1, {(4, 4): [{"item_id": 15, "quantity": 3}]})
    assert index.get_ground_items(1, 1, 1) == []
    assert index.get_ground_items(1, 4, 4)[0]["quantity"] == 3
    assert index.clear_ground_items(1) == 1
    assert index.get_ground_items(2, 2, 2)[0]["quantity"] == 2


def test_reregistering_mutated_npc_cleans_original_tile_and_character() -> None:
    """El modelo mutable no sirve como registro histórico de sus índices."""
    occupation = TileOccupation()
    index = NpcIndex(occupation)
    npc = make_npc("one", 10001)
    index.add_npc(1, npc)
    npc.x, npc.char_index = 2, 10002
    index.add_npc(1, npc)
    assert occupation.get_occupant(1, 1, 1) is None
    assert occupation.get_occupant(1, 2, 1) == "npc:one"
    assert index.get_npc_by_char_index(1, 10001) is None
    assert index.get_npc_by_char_index(1, 10002) is npc
    index.remove_npc(1, "one")
    assert occupation.data == {}
