"""Puertas restauradas y compartidas por jugadores, NPCs y reservas."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from src.game.coordinate_mask import CoordinateMask
from src.game.map_manager import MapManager
from src.repositories.door_repository import DoorRepository
from src.services.map.door_service import DoorService
from src.services.map.door_world import DoorWorld


async def make_world(redis):
    """Construye las tres puertas reales sin cargar el resto del mundo.

    Returns:
        Estado de puertas, mapas y observadores de prueba.
    """
    maps = MapManager()
    maps._map_sizes.update({1: (100, 100), 111: (100, 100)})
    maps._blocked_tiles.update(
        {1: CoordinateMask({(48, 65), (49, 65)}), 111: CoordinateMask({(97, 82)})}
    )
    terrain = SimpleNamespace(
        doors={"map_1": {(48, 65): 5593, (49, 65): 5593}, "map_111": {(97, 82): 9200}},
        resources={
            "map_1": {"blocked": CoordinateMask()},
            "map_111": {"blocked": CoordinateMask({(97, 82)})},
        },
        has_water=lambda *_: False,
    )
    doors = DoorWorld(maps, terrain, DoorRepository(redis), DoorService())
    await doors.restore()
    senders = [AsyncMock(), AsyncMock()]
    for user, sender in enumerate(senders, 1):
        maps.add_player(111, user, sender, f"Prueba{user}")
    return doors, maps, senders


@pytest.mark.asyncio
async def test_open_door_closes_for_both_and_survives_restore(redis_client):
    """La 111(97,82) empieza abierta; el cierre se persiste y ambos lo ven."""
    doors, maps, senders = await make_world(redis_client)
    assert maps.can_move_to(111, 97, 82)
    assert not maps.can_move_to(1, 48, 65)
    with patch("src.services.map.door_world.require_durable", new=AsyncMock()):
        result = await doors.toggle(111, 97, 82)
    assert result["applied"]
    assert not result["is_open"]
    assert await redis_client.get("door:111:97:82") == "247:0"
    for sender in senders:
        sender.send_object_create.assert_awaited_once_with(97, 82, 9194)
        sender.send_block_position.assert_awaited_once_with(97, 82, blocked=True)
    restored, new_maps, _ = await make_world(redis_client)
    assert not new_maps.can_move_to(111, 97, 82)
    newcomer = AsyncMock()
    await restored.snapshot(111, newcomer)
    newcomer.send_block_position.assert_awaited_once_with(97, 82, blocked=True)
    with patch("src.services.map.door_world.require_durable", new=AsyncMock()):
        assert (await restored.toggle(111, 97, 82))["is_open"]
    assert new_maps.can_move_to(111, 97, 82)


@pytest.mark.asyncio
async def test_paired_halves_commit_together_and_reservation_prevents_closing(redis_client):
    """No se cierra una puerta encima de una llegada que ya reservó su destino."""
    doors, maps, _ = await make_world(redis_client)
    with patch("src.services.map.door_world.require_durable", new=AsyncMock()):
        assert (await doors.toggle(1, 48, 65))["is_open"]
        assert await redis_client.get("door:1:48:65") == "7:1"
        assert await redis_client.get("door:1:49:65") == "7:1"
        assert maps.reserve_arrival("arrival", 1, 48, 65)
        assert not (await doors.toggle(1, 49, 65))["applied"]
        assert await redis_client.get("door:1:48:65") == "7:1"
        maps.release_positions("arrival", (1, 48, 65))


@pytest.mark.asyncio
async def test_two_toggles_and_peer_disconnect_keep_confirmed_state(redis_client):
    """La desconexión de un observador no revierte ni interrumpe al otro."""
    doors, maps, senders = await make_world(redis_client)
    senders[0].send_object_create.side_effect = OSError()
    with patch("src.services.map.door_world.require_durable", new=AsyncMock()):
        first, second = await asyncio.gather(doors.toggle(111, 97, 82), doors.toggle(111, 97, 82))
    assert first["applied"]
    assert second["applied"]
    assert not first["is_open"]
    assert second["is_open"]
    assert maps.can_move_to(111, 97, 82)
    assert await redis_client.get("door:111:97:82") == "246:1"
    assert senders[1].send_block_position.await_count == 2


@pytest.mark.asyncio
async def test_arrival_during_durability_check_prevents_closing(redis_client):
    """La comprobación de persistencia puede ceder el turno a una llegada."""
    doors, maps, _ = await make_world(redis_client)

    async def arrive(_raw):
        assert maps.reserve_arrival("late-arrival", 111, 97, 82)

    with patch("src.services.map.door_world.require_durable", side_effect=arrive):
        result = await doors.toggle(111, 97, 82)
    assert not result["applied"]
    maps.release_positions("late-arrival", (111, 97, 82))
    assert maps.can_move_to(111, 97, 82)
    assert await redis_client.get("door:111:97:82") is None
