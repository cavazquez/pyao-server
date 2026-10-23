"""El login reserva su casilla frente a NPCs y otros ingresos concurrentes."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.command_handlers.login_handler import LoginCommandHandler
from src.game.coordinate_mask import CoordinateMask
from src.game.map_manager import MapManager


@pytest.fixture
def login_world():
    """Prepara un mapa real con terreno y servicios de inicialización controlables.

    Returns:
        Mapa, recursos y función para crear un handler por conexión.
    """
    maps = MapManager()
    maps._map_sizes[1] = (100, 100)
    maps._blocked_tiles[1] = CoordinateMask()
    water, trees, mines = set(), set(), set()
    resources = SimpleNamespace(
        has_water=lambda m, x, y: (m, x, y) in water,
        has_tree=lambda m, x, y: (m, x, y) in trees,
        has_mine=lambda m, x, y: (m, x, y) in mines,
        is_blocked=lambda m, x, y: (x, y) in maps._blocked_tiles.get(m, ()),
    )

    def handler():
        sender = MagicMock()
        sender.send_error_msg = AsyncMock()
        sender.send_pos_update = AsyncMock()
        player = MagicMock()
        player.redis.hset = AsyncMock()
        player.set_position = AsyncMock()
        player.is_sailing = AsyncMock(return_value=False)
        result = LoginCommandHandler(
            player,
            MagicMock(),
            maps,
            None,
            None,
            None,
            None,
            SimpleNamespace(map_resources=resources),
            sender,
            {},
        )
        result.init_handler.send_login_packets = AsyncMock(
            return_value={"map": 1, "x": 50, "y": 50, "heading": 3}
        )
        result.init_handler.initialize_player_data = AsyncMock()
        result.init_handler.send_spellbook = AsyncMock()
        result.finalization_handler.finalize_login = AsyncMock()

        async def publish(user_id, username, position):
            maps.add_player(position["map"], user_id, sender, username)
            maps.update_player_tile(
                user_id,
                position["map"],
                position["x"],
                position["y"],
                position["x"],
                position["y"],
            )

        result.spawn_handler.spawn_player = AsyncMock(side_effect=publish)
        return result

    return SimpleNamespace(maps=maps, water=water, trees=trees, mines=mines, handler=handler)


@pytest.mark.parametrize("occupant", ["player:7", "npc:bat", "reservation:other"])
def test_occupied_saved_tile_is_preserved(login_world, occupant):
    """Una llegada alternativa no borra al ocupante original."""
    w = login_world
    w.maps._tile_occupation[1, 50, 50] = occupant
    handler = w.handler().spawn_handler
    saved = {"map": 1, "x": 50, "y": 50, "heading": 3}
    arrived = handler.reserve_spawn_position(saved, "owned")
    assert arrived is not None
    assert arrived != saved
    assert w.maps.get_tile_occupant(1, 50, 50) == occupant
    assert w.maps.get_tile_occupant(1, arrived["x"], arrived["y"]) == "reservation:owned"
    handler.release_spawn_position("other", arrived)
    assert w.maps.get_tile_occupant(1, arrived["x"], arrived["y"]) == "reservation:owned"
    handler.release_spawn_position("owned", arrived)
    assert w.maps.get_tile_occupant(1, arrived["x"], arrived["y"]) is None


@pytest.mark.asyncio
async def test_concurrent_logins_reserve_before_initialization_await(login_world):
    """Dos cuentas con igual posición no publican ni persisten la misma casilla."""
    w = login_world
    first, second = w.handler(), w.handler()
    entered, resume = asyncio.Event(), asyncio.Event()

    async def pause(_user):
        entered.set()
        await resume.wait()

    first.init_handler.initialize_player_data.side_effect = pause
    task = asyncio.create_task(first._complete_login(1, 1, "Primero"))
    try:
        await asyncio.wait_for(entered.wait(), 1)
        assert w.maps.get_tile_occupant(1, 50, 50).startswith("reservation:")
        other = await second._complete_login(2, 1, "Segundo")
        assert other.success
        assert other.data["position"] != {"map": 1, "x": 50, "y": 50, "heading": 3}
        second.player_repo.set_position.assert_awaited_once()
        resume.set()
        assert (await task).success
        assert w.maps.get_tile_occupant(1, 50, 50) == "player:1"
        destination = other.data["position"]
        assert w.maps.get_tile_occupant(1, destination["x"], destination["y"]) == "player:2"
        assert not any(
            value.startswith("reservation:") for value in w.maps._tile_occupation.values()
        )
    finally:
        resume.set()
        await asyncio.gather(task, return_exceptions=True)


@pytest.mark.asyncio
async def test_full_area_rejects_login_without_persisting_or_spawning(login_world):
    """Sin lugar no se utiliza la casilla original ni se publica autenticación."""
    w = login_world
    for x in range(45, 56):
        for y in range(45, 56):
            w.maps._tile_occupation[1, x, y] = f"npc:{x}-{y}"
    before = dict(w.maps._tile_occupation)
    handler = w.handler()
    result = await handler._complete_login(1, 1, "SinLugar")
    assert not result.success
    assert w.maps._tile_occupation == before
    handler.player_repo.set_position.assert_not_awaited()
    handler.spawn_handler.spawn_player.assert_not_awaited()
    handler.message_sender.connection.mark_authenticated.assert_not_called()
    handler.message_sender.connection.close.assert_called_once()
    handler.message_sender.send_error_msg.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("cancel", [False, True])
async def test_initialization_failure_or_cancellation_releases_own_tile(login_world, cancel):
    """Un fallo antes de aparecer nunca deja una reserva fantasma."""
    w = login_world
    handler = w.handler()
    failure = asyncio.CancelledError() if cancel else RuntimeError("fallo sintético")
    handler.init_handler.initialize_player_data.side_effect = failure
    w.maps._tile_occupation[1, 51, 51] = "reservation:other"
    with pytest.raises(type(failure)):
        await handler._complete_login(1, 1, "Fallido")
    assert w.maps._tile_occupation == {(1, 51, 51): "reservation:other"}
    handler.spawn_handler.spawn_player.assert_not_awaited()


def test_relocation_respects_terrain_navigation_and_map_bounds(login_world):
    """Una reserva respeta paredes, recursos, puerta cerrada y medio de navegación."""
    w = login_world
    handler = w.handler().spawn_handler
    w.maps._map_sizes[1] = (3, 3)
    w.water.add((1, 1, 1))
    w.trees.add((1, 1, 2))
    w.mines.add((1, 2, 1))
    w.maps._blocked_tiles[1].add((2, 2))
    w.maps.block_tile(1, 1, 3)
    arrived = handler.reserve_spawn_position({"map": 1, "x": 1, "y": 1}, "land")
    assert arrived == {"map": 1, "x": 2, "y": 3}
    at_sea = handler.reserve_spawn_position({"map": 1, "x": 1, "y": 1}, "sea", sailing=True)
    assert at_sea == {"map": 1, "x": 1, "y": 1}
    assert handler.reserve_spawn_position({"map": 99, "x": 1, "y": 1}, "unknown") is None
