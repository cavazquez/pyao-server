"""Efectos de variantes administrativas y adaptadores nativos del catálogo clásico."""

import time

import pytest

from src.network.packet_id import ServerPacketID
from src.utils.ground_storage import read_ground
from src.utils.redis_config import RedisKeys

from .test_social_commands import chat_messages


@pytest.mark.asyncio
async def test_follow_mimic_and_impersonation_preserve_npc_identity(chat_world):
    """Seguir no domestica; mimetizar conserva al NPC e impersonar ocupa su posición."""
    world = chat_world
    npc = await world.select_npc(2, user=1, x=53, y=53)
    key = RedisKeys.npc_instance(npc.instance_id)
    await world.run("/SEGUIR")
    assert npc.gm_follow_user == 1
    assert await world.redis.hget(key, "gm_follow_user") == "1"
    assert not npc.is_tamed
    await world.run("/SEGUIR")
    assert npc.gm_follow_user == 0
    before = [sender.connection.send.await_count for sender in world.senders.values()]
    assert "apariencia" in await world.run("/MIMETIZAR")
    assert await world.redis.hget(RedisKeys.player_user_stats(1), "morphed_body") == str(
        npc.body_id
    )
    assert await world.redis.exists(key)
    assert all(
        sender.connection.send.await_count > count
        for sender, count in zip(world.senders.values(), before, strict=True)
    )
    assert "apariencia" in await world.run("/IMPERSONAR")
    assert not await world.redis.exists(key)
    position = await world.deps.player_repo.get_position(1)
    assert (position["map"], position["x"], position["y"]) == (2, npc.x, npc.y)


@pytest.mark.asyncio
async def test_respawning_spawn_and_administrative_removal_do_not_grant_loot(chat_world):
    """RACC configura respawn; RMATA lo programa y MASSKILL retira sin premiar al GM."""
    world, maps = chat_world, chat_world.deps.map_manager
    before = {npc.instance_id for npc in maps.get_npcs_in_map(2)}
    stats = await world.deps.player_repo.get_stats(1)
    assert "Creado" in await world.run("/RACC 500")
    npc = next(npc for npc in maps.get_npcs_in_map(2) if npc.instance_id not in before)
    assert npc.respawn_time >= 60
    await world.redis.hset(
        "chat:target:1", mapping={"npc": npc.instance_id, "index": str(npc.char_index)}
    )
    assert "Retirados 1" in await world.run("/RMATA")
    assert npc.instance_id in world.deps.npc_respawn_service._respawn_tasks
    assert not await world.redis.exists(RedisKeys.npc_instance(npc.instance_id))
    await world.run("/MASSKILL")
    assert not maps.get_npcs_in_map(2)
    now = await world.deps.player_repo.get_stats(1)
    assert now["gold"] == stats["gold"]
    assert now.get("experience") == stats.get("experience")


@pytest.mark.asyncio
async def test_npc_voice_map_music_and_ip_queries_have_correct_audiences(chat_world):
    """Voz conserva actor NPC, música usa PLAY_MIDI e IP sólo llega al administrador."""
    world = chat_world
    npc = await world.select_npc(2, user=1)
    await world.run("/TALKAS Bienvenidos al mercado")
    for user in (1, 2, 3):
        message = chat_messages(world.senders[user])[-1]
        assert message["sender_id"] == npc.char_index
        assert message["text"] == "Bienvenidos al mercado"
    assert "3 jugador" in await world.run("/FORCEMIDIMAP 2 2")
    for sender in world.senders.values():
        assert any(
            call.args[0][0] == ServerPacketID.PLAY_MIDI and call.args[0][1] == 2
            for call in sender.connection.send.call_args_list
        )
    assert "127.0.0.2" in await world.run("/NICK2IP Jugador")
    assert "Jugador" in await world.run("/IP2NICK 127.0.0.2")
    assert "127.0.0.2" not in "\n".join(world.senders[3].lines)


@pytest.mark.asyncio
async def test_activity_queries_and_single_tile_deletion_use_live_state(chat_world):
    """Las consultas reflejan oficio/ocultación y DEST borra sólo la casilla propia."""
    world = chat_world
    await world.redis.hset(
        RedisKeys.player_user_stats(2),
        mapping={"work_last_at": str(time.time()), "hidden_until": str(time.time() + 60)},
    )
    assert "Jugador" in await world.run("/TRABAJANDO")
    assert "Jugador" in await world.run("/OCULTANDO")
    await world.run("/CI 2 1")
    assert (await read_ground(world.redis, 2)).tile(50, 49)
    await world.run("/TELEP YO 2 50 49")
    assert "Retirados 1" in await world.run("/DEST")
    assert not (await read_ground(world.redis, 2)).tile(50, 49)
    assert not world.deps.map_manager.get_ground_items(2, 50, 49)


@pytest.mark.asyncio
async def test_text_native_adapters_use_actual_packet_handlers(chat_world):
    """Las rutas de texto comparten el comportamiento de paquetes nativos existentes."""
    world = chat_world
    for command in ("/ONLINE", "/SERVIDOR", "/UPTIME", "/EST", "/PING"):
        before = world.senders[2].connection.send.await_count
        await world.run(command, user=2)
        assert world.senders[2].connection.send.await_count > before, command
    assert any(
        call.args[0][0] == ServerPacketID.PONG
        for call in world.senders[2].connection.send.call_args_list
    )


@pytest.mark.asyncio
async def test_administrative_respawn_policy_survives_the_next_life(chat_world, monkeypatch):
    """Un RACC de plantilla sin respawn conserva el rango también después de reaparecer."""
    world, maps = chat_world, chat_world.deps.map_manager
    before = {npc.instance_id for npc in maps.get_npcs_in_map(2)}
    await world.run("/RACC 500")
    npc = next(npc for npc in maps.get_npcs_in_map(2) if npc.instance_id not in before)
    npc.respawn_time_max = npc.respawn_time + 120
    await world.deps.npc_service.remove_npc(npc)
    respawn = world.deps.npc_respawn_service
    monkeypatch.setattr(respawn, "_find_random_free_position", lambda *_a, **_kw: (56, 56))
    await respawn._respawn_after_delay(npc, 0)
    restored = next(npc for npc in maps.get_npcs_in_map(2) if npc.instance_id not in before)
    assert restored.respawn_time == npc.respawn_time
    assert restored.respawn_time_max == npc.respawn_time_max
    assert restored.role == npc.role
    persisted = await world.redis.hgetall(RedisKeys.npc_instance(restored.instance_id))
    assert persisted["respawn_time"] == str(npc.respawn_time)
    assert persisted["respawn_time_max"] == str(npc.respawn_time_max)


@pytest.mark.asyncio
async def test_exhausted_npc_indices_do_not_publish_invalid_characters(chat_world):
    """Agotar i16 no crea un registro Redis ni publica un CHARACTER_CREATE inválido."""
    world, maps = chat_world, chat_world.deps.map_manager
    world.deps.npc_service._next_char_index = 32768
    before = {npc.instance_id for npc in maps.get_npcs_in_map(2)}
    assert "No se pudo crear" in await world.run("/ACC 500")
    assert {npc.instance_id for npc in maps.get_npcs_in_map(2)} == before
    assert not any(owner.startswith("reservation:") for owner in maps._tile_occupation.values())
