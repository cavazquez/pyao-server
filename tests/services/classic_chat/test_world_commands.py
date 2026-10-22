"""Edición de mapas/NPC con reconstrucción de estado y efectos en ambos observadores."""

import json

import pytest

from src.command_handlers.walk_movement_handler import WalkMovementHandler
from src.services.classic_chat.admin_world import load_overlays, restore_saved_maps
from src.services.classic_chat.world_rules import WORLD_REVISION, prepare
from src.services.combat.physical_plan import PhysicalPlan, PhysicalRequest, commit_physical
from src.services.personal_skills import hide, steal
from src.utils.gold_atomic import operation_id
from src.utils.ground_state import GroundState, stack_identity
from src.utils.ground_storage import encode_fields, read_ground
from src.utils.redis_config import RedisKeys
from src.utils.resource_transaction import Resource


async def select_tile(world, x, y, user=1, map_id=2):
    """Registra la selección del actor para editar una casilla concreta."""
    await world.redis.hset(
        f"chat:target:{user}",
        mapping={
            "npc": "",
            "index": "0",
            "user": "0",
            "map": str(map_id),
            "x": str(x),
            "y": str(y),
        },
    )


@pytest.mark.asyncio
async def test_collision_overlay_is_persisted_used_and_rebuilt_for_reconnect(chat_world):
    """Collision overlay is persisted used and rebuilt for reconnect."""
    world, maps = chat_world, chat_world.deps.map_manager
    await select_tile(world, 54, 54)
    assert "persistido" in await world.run("/BLOQ")
    assert not maps.can_move_to(2, 54, 54)
    assert world.deps.map_resources_service.is_blocked(2, 54, 54)
    maps.tile_overrides.clear()
    maps.overlay_positions.clear()
    await load_overlays(world.deps)
    assert not maps.can_move_to(2, 54, 54)
    before = world.senders[2].connection.send.await_count
    await world.deps.player_map_service._send_terrain_overrides(2, world.senders[2])
    assert world.senders[2].connection.send.await_count > before
    assert "persistido" in await world.run("/BLOQ")
    assert maps.can_move_to(2, 54, 54)
    await select_tile(world, 50, 50)
    assert "ocupada" in await world.run("/BLOQ")


@pytest.mark.asyncio
async def test_portal_radius_and_deletion_use_the_effective_exit_index(chat_world):
    """Portal radius and deletion use the effective exit index."""
    world, maps = chat_world, chat_world.deps.map_manager
    assert "persistido" in await world.run("/CT 3 40 40 2")
    assert maps.get_exit_tile(2, 50, 49) == {"to_map": 3, "to_x": 40, "to_y": 40, "radius": 2}
    movement = WalkMovementHandler(
        world.deps.player_repo,
        maps,
        world.deps.broadcast_service,
        world.deps.player_map_service,
        world.deps.inventory_repo,
        world.deps.map_resources_service,
        world.senders[1],
    )
    x, y, target, changed = await movement._calculate_new_position(1, 50, 50, 2)
    assert changed
    assert target == 3
    assert 38 <= x <= 42
    assert 38 <= y <= 42
    assert (50, 49) in maps.get_exit_positions(2)
    await select_tile(world, 50, 49)
    assert "persistido" in await world.run("/DT")
    assert maps.get_exit_tile(2, 50, 49) is None
    assert (50, 49) not in maps.get_exit_positions(2)
    await load_overlays(world.deps)
    assert maps.get_exit_tile(2, 50, 49) is None


@pytest.mark.asyncio
async def test_roof_weather_night_and_map_metadata_affect_snapshots(chat_world):
    """Roof weather night and map metadata affect snapshots."""
    world = chat_world
    await select_tile(world, 50, 50)
    assert "persistido" in await world.run("/TRIGGER 1")
    assert "activado" in await world.run("/LLUVIA")
    assert not (await world.deps.world_state.weather.snapshot(1))["raining"]
    assert (await world.deps.world_state.weather.snapshot(2))["raining"]
    assert "activado" in await world.run("/NOCHE")
    assert (await world.deps.world_state.weather.snapshot(2))["night"]
    assert "zone = dungeon" in await world.run("/MODMAPINFO ZONA DUNGEON")
    assert not (await world.deps.world_state.weather.snapshot(2))["outdoor"]
    assert "name = Lugar de prueba" in await world.run("/MODMAPINFO NOMBRE Lugar de prueba")
    assert (await world.deps.world_state.weather.snapshot(2))["name"] == "Lugar de prueba"
    assert "music = 2" in await world.run("/MODMAPINFO MUSIC 2")
    await load_overlays(world.deps)
    assert world.deps.map_manager.map_overrides[2]["music"] == "2"


@pytest.mark.asyncio
async def test_rules_and_safe_trigger_reject_before_combat_cost(chat_world):
    """Rules and safe trigger reject before combat cost."""
    world = chat_world
    await world.run("/MODMAPINFO PK 0")
    plan = PhysicalPlan(PhysicalRequest(2, target_player=3), world.deps.item_catalog, 30, 20)
    result = await commit_physical(world.redis, plan, operation_id())
    assert not result["applied"]
    assert "segura" in result["message"]
    assert await world.redis.hget(RedisKeys.player_user_stats(2), "min_sta") == "100"
    await world.run("/MODMAPINFO PK 1")
    await select_tile(world, 50, 51)
    await world.run("/TRIGGER 4")
    plan = PhysicalPlan(PhysicalRequest(2, target_player=3), world.deps.item_catalog, 30, 20)
    assert not (await commit_physical(world.redis, plan, operation_id()))["applied"]
    assert await world.redis.hget(RedisKeys.player_user_stats(2), "min_sta") == "100"
    result = await steal(
        world.deps.player_repo,
        world.deps.inventory_repo,
        world.deps.item_catalog,
        2,
        3,
        operation_id(),
    )
    assert not result["applied"]
    assert "zona" in result["message"]


@pytest.mark.asyncio
async def test_rule_revision_prevents_using_a_stale_action_snapshot(chat_world):
    """Rule revision prevents using a stale action snapshot."""
    world = chat_world
    plan = PhysicalPlan(PhysicalRequest(2, target_player=3), world.deps.item_catalog, 30, 20)
    plan.world = await prepare(world.redis, 2)
    plan.resources = (*plan.resources, Resource(WORLD_REVISION, "string"))
    await world.run("/MODMAPINFO PK 0")
    result = await commit_physical(world.redis, plan, operation_id())
    assert not result["applied"]
    assert "cambiaron" in result["message"]
    assert await world.redis.hget(RedisKeys.player_user_stats(2), "min_sta") == "100"
    await world.run("/MODMAPINFO OCULTARSINEFECTO 1")
    result = await hide(world.deps.player_repo, 2, operation_id())
    assert not result["applied"]
    assert "ocultarte" in result["message"]


@pytest.mark.asyncio
async def test_ground_creation_area_cleanup_and_all_map_cleanup(chat_world):
    """Ground creation area cleanup and all map cleanup."""
    world, maps = chat_world, chat_world.deps.map_manager
    assert "Creado 1" in await world.run("/CI 2 5")
    ground = await read_ground(world.redis, 2)
    assert ground.tile(50, 49)[0]["item_id"] == 2
    assert ground.tile(50, 49)[0]["quantity"] == 5
    assert maps.get_ground_items(2, 50, 49)[0]["quantity"] == 5
    assert "Retirados 1" in await world.run("/MASSDEST")
    assert not (await read_ground(world.redis, 2)).positions()
    other = GroundState(3, None)
    other.append(
        40,
        40,
        {"item_id": 2, "quantity": 1, "stack_id": stack_identity("other-map"), "grh_index": 1},
    )
    await world.redis.hset(RedisKeys.ground_items(3), mapping=encode_fields(other))
    assert "Retirados 1" in await world.run("/LIMPIAR")
    assert not (await read_ground(world.redis, 3)).positions()


@pytest.mark.asyncio
async def test_npc_reservations_spawn_remove_and_restoration_of_dialog(chat_world):
    """Npc reservations spawn remove and restoration of dialog."""
    world, maps = chat_world, chat_world.deps.map_manager
    before = {npc.instance_id for npc in maps.get_npcs_in_map(2)}
    assert "Creado" in await world.run("/ACC 500")
    created = next(npc for npc in maps.get_npcs_in_map(2) if npc.instance_id not in before)
    assert created.respawn_time == 0
    assert maps.get_tile_occupant(2, created.x, created.y) == f"npc:{created.instance_id}"
    await world.redis.hset(
        "chat:target:1", mapping={"npc": created.instance_id, "index": str(created.char_index)}
    )
    assert "Diálogo actualizado" in await world.run("/SETDIALOG Diálogo de prueba")
    assert created.description == "Diálogo de prueba"
    assert "Checkpoint" in await world.run("/GUARDAMAPA")
    assert "Retirad" in await world.run("/MATA")
    assert not await world.redis.exists(RedisKeys.npc_instance(created.instance_id))
    await restore_saved_maps(world.deps)
    restored = next(
        npc for npc in maps.get_npcs_in_map(2) if npc.description == "Diálogo de prueba"
    )
    assert restored.instance_id != created.instance_id
    assert restored.respawn_time == 0
    assert (
        await world.redis.hget(RedisKeys.npc_instance(restored.instance_id), "description")
        == restored.description
    )


@pytest.mark.asyncio
async def test_invalid_checkpoint_is_rejected_before_removing_live_npcs(chat_world):
    """Un diálogo corrupto en Redis no elimina los NPC cargados al restaurar."""
    world, maps = chat_world, chat_world.deps.map_manager
    await world.run("/GUARDAMAPA")
    key = "world:map:saved:2"
    checkpoint = json.loads(await world.redis.get(key))
    assert checkpoint["npcs"]
    checkpoint["npcs"][0]["description"] = {"invalid": "dialog"}
    await world.redis.set(key, json.dumps(checkpoint))
    before = {npc.instance_id for npc in maps.get_npcs_in_map(2)}
    with pytest.raises(ValueError, match="Checkpoint de configuración inválido"):
        await restore_saved_maps(world.deps)
    assert {npc.instance_id for npc in maps.get_npcs_in_map(2)} == before
    assert all([await world.redis.exists(RedisKeys.npc_instance(identity)) for identity in before])


@pytest.mark.asyncio
async def test_reset_merchant_inventory_reads_only_redis_policy(chat_world):
    """Reset merchant inventory reads only redis policy."""
    world = chat_world
    await world.select_npc(2, user=1)
    await world.redis.hset(
        RedisKeys.merchant_inventory(2), mapping={"slot_1": "2:1", "stale": "bad"}
    )
    assert "repuesto" in await world.run("/RESETINV")
    stock = await world.redis.hgetall(RedisKeys.merchant_inventory(2))
    assert stock == {"slot_1": "2:20", "slot_2": "38:10"}
    assert await world.redis.smembers("merchant:2:items") == {"2", "38"}


@pytest.mark.asyncio
async def test_pretorian_group_has_real_templates_and_no_reservation_leaks(chat_world):
    """Pretorian group has real templates and no reservation leaks."""
    world, maps = chat_world, chat_world.deps.map_manager
    assert "12 NPC" in await world.run("/CREARPRETORIANOS 3 50 50")
    rows = maps.get_npcs_in_map(3)
    assert len(rows) == 12
    assert all(npc.role == "pretorian" and npc.respawn_time == 0 for npc in rows)
    assert "Ya hay" in await world.run("/CREARPRETORIANOS 3 50 50")
    assert "Retirados 12" in await world.run("/ELIMINARPRETORIANOS 3")
    assert not maps.get_npcs_in_map(3)
    assert not any(owner.startswith("reservation:") for owner in maps._tile_occupation.values())


@pytest.mark.asyncio
async def test_sound_and_music_ids_fit_the_packet_and_audience(chat_world):
    """Sound and music ids fit the packet and audience."""
    world = chat_world
    before = [sender.connection.send.await_count for sender in world.senders.values()]
    assert "3 jugador" in await world.run("/FORCEWAVMAP 2 2 50 50")
    assert all(
        sender.connection.send.await_count > count
        for sender, count in zip(world.senders.values(), before, strict=True)
    )
    assert "3 jugador" in await world.run("/FORCEMIDI 2")
    assert "entre 0 y 255" in await world.run("/FORCEWAV 256")
