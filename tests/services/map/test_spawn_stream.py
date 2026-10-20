"""El spawn conserva orden y contenido sin demoras por entidad ni doble snapshot."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.command_handlers.login_spawn_handler import LoginSpawnHandler
from src.game.map_manager import MapManager
from src.services.map.player_map_service import ENTITY_SEND_BATCH, PlayerMapService


@pytest.mark.asyncio
async def test_login_loads_ground_and_sends_one_complete_spawn_in_order() -> None:
    """Mapa, posición y snapshot aparecen una vez, con suelo cargado antes de publicarlo."""
    sender, maps, service = MagicMock(), MagicMock(), MagicMock()
    parent = MagicMock()
    sender.play_sound_login = AsyncMock()
    sender.play_effect_spawn = AsyncMock()
    maps.load_ground_items = AsyncMock()
    sender.send_change_map = AsyncMock()
    sender.send_pos_update = AsyncMock()
    service.spawn_in_map = AsyncMock()
    parent.attach_mock(maps.load_ground_items, "load")
    parent.attach_mock(sender.send_change_map, "map")
    parent.attach_mock(sender.send_pos_update, "position")
    parent.attach_mock(service.spawn_in_map, "spawn")
    parent.attach_mock(sender.play_sound_login, "sound")
    handler = LoginSpawnHandler(MagicMock(), MagicMock(), maps, service, sender)
    position = {"map": 1, "x": 100, "y": 1, "heading": 2}
    await handler.spawn_player(7, "Fixture", position)
    assert [call[0] for call in parent.mock_calls] == ["load", "map", "position", "spawn", "sound"]
    maps.load_ground_items.assert_awaited_once_with(1)
    service.spawn_in_map.assert_awaited_once_with(
        user_id=7, map_id=1, x=100, y=1, heading=2, message_sender=sender
    )
    service.transition_to_map.assert_not_called()


@pytest.mark.asyncio
async def test_login_effect_reaches_current_map_once_after_character_creation() -> None:
    """El efecto llega después del actor; un peer cerrado no corta el resto del mapa."""
    maps = MapManager()
    owner, broken, peer, other_map = (MagicMock() for _ in range(4))
    for user, sender in enumerate((owner, broken, peer, other_map), start=1):
        sender.play_effect_spawn = AsyncMock()
        maps.add_player(2 if sender is other_map else 1, user, sender)
    owner.play_sound_login = AsyncMock()
    owner.send_change_map = AsyncMock()
    owner.send_pos_update = AsyncMock()
    broken.play_effect_spawn.side_effect = ConnectionError("peer cerrado")
    calls = MagicMock()
    calls.attach_mock(owner.play_effect_spawn, "owner")
    calls.attach_mock(peer.play_effect_spawn, "peer")
    service = MagicMock(spawn_in_map=AsyncMock())
    calls.attach_mock(service.spawn_in_map, "character_creation")
    handler = LoginSpawnHandler(MagicMock(), MagicMock(), maps, service, owner)
    await handler.spawn_player(1, "Fixture", {"map": 1, "x": 50, "y": 50})
    assert [call[0] for call in calls.mock_calls] == ["character_creation", "owner", "peer"]
    for sender in (owner, broken, peer):
        sender.play_effect_spawn.assert_awaited_once_with(char_index=1)
    other_map.play_effect_spawn.assert_not_awaited()


@pytest.mark.asyncio
async def test_npc_stream_preserves_all_entities_and_only_yields_cooperatively() -> None:
    """Muchos NPCs no agregan 10 ms por actor; se cede el loop en lotes acotados."""
    maps, sender = MagicMock(), MagicMock()
    npcs = [MagicMock(char_index=10001 + index) for index in range(300)]
    maps.get_npcs_in_map.return_value = npcs
    sender.send_character_create = AsyncMock()
    service = PlayerMapService(
        player_repo=MagicMock(),
        account_repo=MagicMock(),
        map_manager=maps,
        broadcast_service=MagicMock(),
    )
    with patch(
        "src.services.map.player_map_service.asyncio.sleep", new_callable=AsyncMock
    ) as sleep:
        assert await service._send_npcs_in_map(1, sender) == 300
    assert sleep.await_count == 300 // ENTITY_SEND_BATCH
    assert all(call.args == (0,) for call in sleep.await_args_list)
    assert [call.kwargs["char_index"] for call in sender.send_character_create.await_args_list] == [
        npc.char_index for npc in npcs
    ]
