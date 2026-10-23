"""Intercalados que antes permitían pisar una llegada durante un await de Redis."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.command_handlers.login_spawn_handler import LoginSpawnHandler
from src.command_handlers.walk_movement_handler import WalkMovementHandler
from src.game.coordinate_mask import CoordinateMask
from src.game.map_manager import MapManager
from src.services.npc.npc_service import NPCService


@pytest.fixture
def moving_world():
    """Prepara ocupación real y servicios con la persistencia controlable.

    Yields:
        Mapa, jugador, NPC y handlers reales del ensayo.
    """
    NPCService.reset_instance()
    maps = MapManager()
    maps._map_sizes[1] = (100, 100)
    maps._blocked_tiles[1] = CoordinateMask()
    player = MagicMock()
    player.get_position = AsyncMock(return_value={"map": 1, "x": 50, "y": 50, "heading": 2})
    player.set_position = AsyncMock()
    player.redis.hset = AsyncMock()
    sender = MagicMock(send_pos_update=AsyncMock())
    walk = WalkMovementHandler(player, maps, None, None, None, None, sender)
    npc = SimpleNamespace(
        instance_id="moving", name="Prueba", map_id=1, x=50, y=50, heading=2, char_index=10001
    )
    repo = MagicMock(update_npc_position=AsyncMock())
    service = NPCService(repo, MagicMock(), maps, AsyncMock())
    login = LoginSpawnHandler(player, MagicMock(), maps, None, sender)
    try:
        yield SimpleNamespace(
            maps=maps,
            player=player,
            walk=walk,
            sender=sender,
            npc=npc,
            repo=repo,
            service=service,
            login=login,
        )
    finally:
        NPCService.reset_instance()


def reserve_login(world):
    """Reserva la misma casilla que intentó usar el actor en movimiento.

    Returns:
        Llegada efectiva que eligió el login.
    """
    result = world.login.reserve_spawn_position({"map": 1, "x": 51, "y": 50}, "login")
    assert result is not None
    return result


@pytest.mark.asyncio
@pytest.mark.parametrize("actor", ["player", "npc"])
async def test_move_in_redis_reserves_destination_against_login(moving_world, actor):
    """La casilla sigue protegida mientras el comando de persistencia está esperando."""
    w = moving_world
    identity = "player:1" if actor == "player" else "npc:moving"
    w.maps._tile_occupation[1, 50, 50] = identity
    entered, resume = asyncio.Event(), asyncio.Event()

    async def pause(*_args: object) -> None:
        entered.set()
        await resume.wait()

    if actor == "player":
        w.player.set_position.side_effect = pause
        action = w.walk.execute_movement(1, 2, 50, 50, 1)
    else:
        w.repo.update_npc_position.side_effect = pause
        action = w.service.move_npc(w.npc, 51, 50, 2)
    task = asyncio.create_task(action)
    try:
        await asyncio.wait_for(entered.wait(), 1)
        occupant = w.maps.get_tile_occupant(1, 51, 50)
        assert occupant is not None
        assert occupant.startswith("reservation:")
        arrived = reserve_login(w)
        assert (arrived["x"], arrived["y"]) != (51, 50)
        w.maps.update_player_tile(2, 1, arrived["x"], arrived["y"], arrived["x"], arrived["y"])
        resume.set()
        await task
        assert w.maps.get_tile_occupant(1, 51, 50) == identity
        assert w.maps.get_tile_occupant(1, arrived["x"], arrived["y"]) == "player:2"
        assert not any(v.startswith("reservation:") for v in w.maps._tile_occupation.values())
    finally:
        resume.set()
        await asyncio.gather(task, return_exceptions=True)


@pytest.mark.asyncio
async def test_login_between_collision_check_and_position_read_blocks_walk(moving_world):
    """La validación anterior no autoriza pisar una casilla que cambió durante la lectura."""
    w = moving_world
    w.maps._tile_occupation[1, 50, 50] = "player:1"
    entered, resume = asyncio.Event(), asyncio.Event()

    async def pause(_user):
        entered.set()
        await resume.wait()
        return {"map": 1, "x": 50, "y": 50, "heading": 2}

    w.player.get_position.side_effect = pause
    task = asyncio.create_task(w.walk.execute_movement(1, 2, 50, 50, 1))
    try:
        await asyncio.wait_for(entered.wait(), 1)
        assert reserve_login(w) == {"map": 1, "x": 51, "y": 50}
        w.maps.update_player_tile(2, 1, 51, 50, 51, 50)
        resume.set()
        assert (await task)[2] == {"moved": False, "blocked": True}
        w.player.set_position.assert_not_awaited()
        w.sender.send_pos_update.assert_awaited_once_with(50, 50)
        assert w.maps.get_tile_occupant(1, 51, 50) == "player:2"
    finally:
        resume.set()
        await asyncio.gather(task, return_exceptions=True)


@pytest.mark.asyncio
@pytest.mark.parametrize("actor", ["player", "npc"])
@pytest.mark.parametrize("cancel", [False, True])
async def test_persistence_failure_releases_only_owned_destination(moving_world, actor, cancel):
    """Error y cancelación dejan el origen y las reservas ajenas intactos."""
    w = moving_world
    identity = "player:1" if actor == "player" else "npc:moving"
    w.maps._tile_occupation.update({(1, 50, 50): identity, (1, 60, 60): "reservation:other"})
    failure = asyncio.CancelledError() if cancel else RuntimeError("fallo sintético")
    if actor == "player":
        w.player.set_position.side_effect = failure
        action = w.walk.execute_movement(1, 2, 50, 50, 1)
    else:
        w.repo.update_npc_position.side_effect = failure
        action = w.service.move_npc(w.npc, 51, 50, 2)
    with pytest.raises(type(failure)):
        await action
    assert dict(w.maps._tile_occupation) == {
        (1, 50, 50): identity,
        (1, 60, 60): "reservation:other",
    }
    assert not w.service._moving_npcs


@pytest.mark.asyncio
async def test_same_npc_cannot_start_a_second_move_while_persisting(moving_world):
    """IA y seguimiento de mascota no pueden mover simultáneamente la misma instancia."""
    w = moving_world
    w.maps._tile_occupation[1, 50, 50] = "npc:moving"
    entered, resume = asyncio.Event(), asyncio.Event()

    async def pause(*_args: object) -> None:
        entered.set()
        await resume.wait()

    w.repo.update_npc_position.side_effect = pause
    task = asyncio.create_task(w.service.move_npc(w.npc, 51, 50, 2))
    try:
        await asyncio.wait_for(entered.wait(), 1)
        await w.service.move_npc(w.npc, 50, 51, 3)
        w.repo.update_npc_position.assert_awaited_once()
        assert w.maps.get_tile_occupant(1, 50, 51) is None
        resume.set()
        await task
        assert (w.npc.x, w.npc.y) == (51, 50)
        assert not w.service._moving_npcs
    finally:
        resume.set()
        await asyncio.gather(task, return_exceptions=True)


@pytest.mark.parametrize("actor", ["player", "npc"])
@pytest.mark.parametrize("other", ["player:9", "npc:other", "reservation:other"])
def test_late_origin_cleanup_preserves_another_occupant(moving_world, actor, other):
    """Una limpieza tardía no borra la nueva ocupación del origen."""
    w = moving_world
    w.maps._tile_occupation[1, 50, 50] = other
    if actor == "player":
        w.maps.update_player_tile(1, 1, 50, 50, 51, 50)
    else:
        w.maps.update_npc_tile("moving", 1, 50, 50, 51, 50)
    assert w.maps.get_tile_occupant(1, 50, 50) == other


@pytest.mark.asyncio
async def test_npc_forbidden_trigger_rejects_before_persisting(moving_world):
    """Un trigger prohibido no cambia primero la posición guardada."""
    w = moving_world
    w.maps.tile_overrides[1, 51, 50] = {"trigger": 3}
    await w.service.move_npc(w.npc, 51, 50, 2)
    w.repo.update_npc_position.assert_not_awaited()
    assert (w.npc.x, w.npc.y) == (50, 50)
