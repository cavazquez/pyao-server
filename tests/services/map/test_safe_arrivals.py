"""Llegadas con Redis real del fixture, reservas y transporte que puede fallar."""

import asyncio
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.game.coordinate_mask import CoordinateMask
from src.game.map_manager import MapManager
from src.services.map.player_map_service import PlayerMapService
from src.services.map.transfer import commit_transfer
from src.utils.redis_config import RedisKeys


@pytest.fixture
def arrivals(mechanics_world):
    """Dos mapas pequeños y un actor, con repositorio transaccional del fixture.

    Returns:
        Servicio, mapas y estados controlables del ensayo.
    """
    world = mechanics_world
    world.maps = MapManager()
    world.maps._map_sizes.update({2: (100, 100), 3: (100, 100)})
    world.maps._blocked_tiles.update({2: CoordinateMask(), 3: CoordinateMask()})
    world.sender = AsyncMock()
    world.sender.connection = MagicMock()
    world.maps.add_player(2, 1, world.sender, "Prueba1")
    world.maps.update_player_tile(1, 2, 50, 50, 50, 50)
    world.water, world.solid, world.trees = set(), set(), set()
    terrain = SimpleNamespace(
        has_water=lambda m, x, y: (m, x, y) in world.water,
        is_blocked=lambda m, x, y: (m, x, y) in world.solid,
        has_tree=lambda m, x, y: (m, x, y) in world.trees,
        has_mine=lambda *_: False,
        workshops={},
    )
    world.service = PlayerMapService(
        world.player,
        AsyncMock(get_account_by_user_id=AsyncMock(return_value={"username": "Prueba1"})),
        world.maps,
        AsyncMock(),
        map_resources=terrain,
    )
    return world


async def cross(world, user=1, destination=(3, 20, 20)):
    """Usa el servicio público que comparten WALK y GM.

    Returns:
        Si la llegada se confirmó.
    """
    return await world.service.transition_to_map(user, 2, 50, 50, *destination, 2, world.sender)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "obstacle", ["player", "npc", "reservation", "wall", "door", "tree", "unknown", "bounds"]
)
async def test_rejected_arrival_keeps_origin_and_does_not_publish_map(arrivals, obstacle):
    """Cada impedimento conserva Redis, pertenencia y ocupante del destino."""
    w = arrivals
    target = (3, 20, 20)
    if obstacle in {"player", "npc", "reservation"}:
        w.maps._tile_occupation[target] = f"{obstacle}:other"
    elif obstacle == "wall":
        w.maps._blocked_tiles[3].add((20, 20))
    elif obstacle == "door":
        w.maps.block_tile(3, 20, 20)
    elif obstacle == "tree":
        w.trees.add(target)
    elif obstacle == "unknown":
        target = (999, 20, 20)
    else:
        target = (3, 0, 20)
    assert not await cross(w, destination=target)
    assert await w.player.get_position(1) == {"map": 2, "x": 50, "y": 50, "heading": 2}
    assert 1 in w.maps.get_players_in_map(2)
    assert not w.maps.get_players_in_map(3)
    w.sender.send_change_map.assert_not_awaited()
    if obstacle in {"player", "npc", "reservation"}:
        assert w.maps._tile_occupation[target] == f"{obstacle}:other"


@pytest.mark.asyncio
async def test_reservation_survives_redis_await_and_blocks_other_arrival(arrivals):
    """Dos llegadas simultáneas no pueden confirmar la misma casilla."""
    w = arrivals
    await w.redis.hset(RedisKeys.player_position(2), mapping={"map": 2, "x": 50, "y": 50})
    entered, resume = asyncio.Event(), asyncio.Event()

    async def delayed(*args: object, **kwargs: object):
        entered.set()
        await resume.wait()
        return await commit_transfer(*args, **kwargs)

    with patch("src.services.map.player_map_service.commit_transfer", delayed):
        first = asyncio.create_task(cross(w))
        await asyncio.wait_for(entered.wait(), 1)
        assert not await cross(w, user=2)
        resume.set()
        assert await first
    assert (await w.player.get_position(1))["map"] == 3
    assert (await w.player.get_position(2))["map"] == 2
    assert w.maps._tile_occupation[3, 20, 20] == "player:1"


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["alive", "pending", "cancelled", "replaced", "future"])
async def test_home_arrival_rechecks_life_and_deadline_before_commit(arrivals, change):
    """Un plazo observado no puede trasladar una vida nueva ni cancelar otro regreso."""
    w = arrivals
    deadline = time.time() + (60 if change == "future" else -1)
    state = {"min_hp": "0", "death_state": "complete", "home_due": str(deadline)}
    if change == "alive":
        state["min_hp"] = "1"
    elif change == "pending":
        state["death_state"] = "pending"
    elif change == "cancelled":
        state["home_due"] = "0"
    elif change == "replaced":
        state["home_due"] = str(deadline + 120)
    await w.redis.hset(RedisKeys.player_user_stats(1), mapping=state)
    assert not await w.service.transition_to_map(
        1, 2, 50, 50, 3, 20, 20, 2, w.sender, home_deadline=deadline
    )
    assert (await w.player.get_position(1))["map"] == 2
    assert await w.redis.hget(RedisKeys.player_user_stats(1), "home_due") == state["home_due"]
    assert w.maps.get_tile_occupant(2, 50, 50) == "player:1"
    assert w.maps.get_tile_occupant(3, 20, 20) is None
    w.sender.send_change_map.assert_not_awaited()


@pytest.mark.asyncio
async def test_atomic_commit_precedes_transport_and_disconnect_preserves_destination(arrivals):
    """Un fallo de transporte posterior no revierte ni pierde la ocupación confirmada."""
    w = arrivals

    async def fail(_map):
        assert (await w.player.get_position(1))["map"] == 3
        assert w.maps._tile_occupation[3, 20, 20] == "player:1"
        message = "connection closed in fixture"
        raise OSError(message)

    w.sender.send_change_map.side_effect = fail
    assert await cross(w)
    assert (await w.player.get_position(1))["map"] == 3
    assert 1 not in w.maps.get_players_in_map(2)
    assert 1 in w.maps.get_players_in_map(3)
    w.sender.connection.close.assert_called_once()
    w.service.broadcast_service.broadcast_character_remove.assert_awaited_once_with(2, 1)


@pytest.mark.asyncio
async def test_changed_origin_releases_only_own_reservation(arrivals):
    """Un snapshot distinto del origen cancela sin dejar reservas colgadas."""
    w = arrivals
    await w.redis.hset(RedisKeys.player_position(1), "x", 49)
    assert not await cross(w)
    assert (await w.player.get_position(1))["x"] == 49
    assert (3, 20, 20) not in w.maps._tile_occupation


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["no_boat", "skill", "dead"])
async def test_water_requires_alive_boat_and_navigation_in_same_snapshot(arrivals, failure):
    """No hay cambio parcial de navegación, posición o inventario al rechazar."""
    w = arrivals
    w.water.add((3, 20, 20))
    await w.redis.hset(RedisKeys.player_inventory(1), "slot_1", "474:1")
    await w.redis.hset(RedisKeys.player_skills(1), "level:navegacion", 100)
    if failure == "no_boat":
        await w.redis.delete(RedisKeys.player_inventory(1))
    elif failure == "skill":
        await w.redis.hset(RedisKeys.player_skills(1), "level:navegacion", 0)
    else:
        await w.redis.hset(RedisKeys.player_user_stats(1), "min_hp", 0)
    before = await w.redis.hgetall(RedisKeys.player_inventory(1))
    assert not await cross(w)
    assert (await w.player.get_position(1))["map"] == 2
    assert await w.redis.hgetall(RedisKeys.player_inventory(1)) == before


@pytest.mark.asyncio
async def test_embark_and_same_map_disembark_keep_boat_and_publish_toggle(arrivals):
    """El mismo camino confirma agua y tierra y conserva la embarcación real."""
    w = arrivals
    w.water.add((3, 20, 20))
    await w.redis.hset(RedisKeys.player_inventory(1), "slot_1", "474:1")
    await w.redis.hset(RedisKeys.player_skills(1), "level:navegacion", 100)
    assert await cross(w)
    assert await w.redis.hget(RedisKeys.player_user_stats(1), "sailing") == "1"
    assert await w.service.teleport_in_same_map(1, 3, 20, 20, 21, 20, 2, w.sender)
    assert await w.redis.hget(RedisKeys.player_user_stats(1), "sailing") == "0"
    assert await w.redis.hget(RedisKeys.player_inventory(1), "slot_1") == "474:1"
    assert w.sender.send_navigate_toggle.await_count == 2


@pytest.mark.asyncio
async def test_portal_override_precedes_local_actor_and_never_opens_closed_door(arrivals):
    """El desbloqueo sólo afecta portales y se publica antes del actor interactivo."""
    w = arrivals
    w.solid.update({(3, 9, 9), (3, 10, 9), (3, 11, 9)})
    destination = {"to_map": 2, "to_x": 20, "to_y": 20}
    w.maps._exit_index.update({(3, 9, 9): destination, (3, 10, 9): destination})
    w.maps.block_tile(3, 10, 9)
    assert await cross(w)
    w.sender.send_block_position.assert_awaited_once_with(9, 9, blocked=False)
    calls = [call[0] for call in w.sender.mock_calls]
    assert (
        calls.index("send_change_map")
        < calls.index("send_block_position")
        < calls.index("send_character_create")
    )
