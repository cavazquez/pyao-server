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
from src.utils.resource_transaction import transact


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


@pytest.mark.asyncio
async def test_failed_transaction_releases_temporary_collision(redis_client):
    """Un fallo anterior al EXEC conserva la puerta abierta y su gráfico."""
    doors, maps, senders = await make_world(redis_client)
    with (
        patch("src.services.map.door_world.require_durable", new=AsyncMock()),
        patch("src.services.map.door_world.transact", side_effect=RuntimeError("sin commit")),
        pytest.raises(RuntimeError, match="sin commit"),
    ):
        await doors.toggle(111, 97, 82)
    assert maps.can_move_to(111, 97, 82)
    assert not doors.pending
    assert await redis_client.get("door:111:97:82") is None
    for sender in senders:
        sender.send_block_position.assert_awaited_once_with(97, 82, blocked=False)


@pytest.mark.asyncio
async def test_uncertain_reply_recovers_committed_state_without_toggling_again(redis_client):
    """Perder la respuesta del commit no reabre ni duplica la operación."""
    doors, maps, senders = await make_world(redis_client)

    async def lose_reply(raw, resources, identity, request, decide):
        await transact(raw, resources, identity, request, decide)
        message = "respuesta perdida"
        raise RuntimeError(message)

    with (
        patch("src.services.map.door_world.require_durable", new=AsyncMock()),
        patch("src.services.map.door_world.transact", side_effect=lose_reply) as transaction,
        pytest.raises(RuntimeError, match="respuesta perdida"),
    ):
        await doors.toggle(111, 97, 82)
    assert transaction.await_count == 1
    assert not maps.can_move_to(111, 97, 82)
    assert not doors.pending
    assert await redis_client.get("door:111:97:82") == "247:0"
    for sender in senders:
        sender.send_block_position.assert_awaited_once_with(97, 82, blocked=True)


@pytest.mark.asyncio
async def test_disconnected_redis_reconciles_paired_door_on_next_snapshot(redis_client):
    """Sin Redis se bloquea; al recuperar, ambas mitades vuelven al commit real."""
    doors, maps, senders = await make_world(redis_client)

    async def lose_reply(raw, resources, identity, request, decide):
        await transact(raw, resources, identity, request, decide)
        message = "respuesta perdida"
        raise RuntimeError(message)

    with (
        patch("src.services.map.door_world.require_durable", new=AsyncMock()),
        patch("src.services.map.door_world.transact", side_effect=lose_reply),
        patch.object(redis_client.redis, "mget", side_effect=OSError("sin Redis")),
        pytest.raises(RuntimeError, match="respuesta perdida"),
    ):
        await doors.toggle(1, 48, 65)
    assert not maps.can_move_to(1, 48, 65)
    assert not maps.can_move_to(1, 49, 65)
    assert doors.pending[1] == {(48, 65), (49, 65)}
    newcomer = AsyncMock()
    await doors.snapshot(1, newcomer)
    assert not doors.pending
    for x in (48, 49):
        assert maps.can_move_to(1, x, 65)
        assert await redis_client.get(f"door:1:{x}:65") == "7:1"
        newcomer.send_block_position.assert_any_await(x, 65, blocked=False)
    assert not any(sender.send_block_position.await_count for sender in senders)


@pytest.mark.asyncio
async def test_cancellation_waits_for_commit_and_broadcast(redis_client):
    """Cancelar el clic no deja la transacción o su colisión a medio aplicar."""
    doors, maps, senders = await make_world(redis_client)
    started, finish = asyncio.Event(), asyncio.Event()

    async def paused_transaction(raw, resources, identity, request, decide):
        started.set()
        await finish.wait()
        return await transact(raw, resources, identity, request, decide)

    with (
        patch("src.services.map.door_world.require_durable", new=AsyncMock()),
        patch("src.services.map.door_world.transact", side_effect=paused_transaction),
    ):
        task = asyncio.create_task(doors.toggle(111, 97, 82))
        await started.wait()
        task.cancel()
        await asyncio.sleep(0)
        assert not task.done()
        finish.set()
        with pytest.raises(asyncio.CancelledError):
            await task
    assert await redis_client.get("door:111:97:82") == "247:0"
    assert not maps.can_move_to(111, 97, 82)
    assert not doors.pending
    for sender in senders:
        sender.send_block_position.assert_awaited_once_with(97, 82, blocked=True)


@pytest.mark.asyncio
async def test_late_durability_error_still_publishes_confirmed_collision(redis_client):
    """Una confirmación AOF tardía no deja los clientes con el estado anterior."""
    doors, maps, senders = await make_world(redis_client)
    with (
        patch(
            "src.services.map.door_world.require_durable", side_effect=[None, RuntimeError("AOF")]
        ),
        pytest.raises(RuntimeError, match="AOF"),
    ):
        await doors.toggle(111, 97, 82)
    assert not maps.can_move_to(111, 97, 82)
    assert not doors.pending
    for sender in senders:
        sender.send_block_position.assert_awaited_once_with(97, 82, blocked=True)


@pytest.mark.asyncio
async def test_lost_nondurable_commit_restores_catalogue_default(redis_client):
    """Si se perdió el último commit, no se reutiliza su caché como valor inicial."""
    doors, maps, senders = await make_world(redis_client)
    calls = 0

    async def lose_nondurable_commit(_raw):
        nonlocal calls
        calls += 1
        if calls == 2:
            await redis_client.delete("door:111:97:82")
            message = "AOF perdido"
            raise RuntimeError(message)

    with (
        patch("src.services.map.door_world.require_durable", side_effect=lose_nondurable_commit),
        pytest.raises(RuntimeError, match="AOF perdido"),
    ):
        await doors.toggle(111, 97, 82)
    assert maps.can_move_to(111, 97, 82)
    assert not doors.pending
    for sender in senders:
        sender.send_block_position.assert_awaited_once_with(97, 82, blocked=False)
