"""Servicios de ciudad, descanso, facciones, mascotas y solicitudes de party."""

import time

import pytest

from src.models.items_catalog import ITEMS_CATALOG
from src.services.classic_chat.jobs import ClassicActionsEffect
from src.utils.redis_config import RedisKeys


@pytest.mark.asyncio
async def test_bank_commands_use_selected_banker_and_preserve_total(chat_world):
    """Bank commands use selected banker and preserve total."""
    world = chat_world
    await world.select_npc(5)
    text = await world.run("/BOVEDA", user=2)
    assert "No se pudo" not in text
    assert "100" in await world.run("/DEPOSITAR 100", user=2)
    assert await world.redis.hget(RedisKeys.player_user_stats(2), "gold") == "900"
    assert await world.deps.bank_repo.get_gold(2) == 100
    assert "100" in await world.run("/BALANCE", user=2)
    assert "50" in await world.run("/RETIRAR 50", user=2)
    assert await world.redis.hget(RedisKeys.player_user_stats(2), "gold") == "950"
    assert await world.deps.bank_repo.get_gold(2) == 50


@pytest.mark.asyncio
async def test_priest_heals_and_revives_using_the_shared_lifecycle(chat_world):
    """Priest heals and revives using the shared lifecycle."""
    world = chat_world
    await world.select_npc(81)
    key = RedisKeys.player_user_stats(2)
    await world.redis.hset(key, "min_hp", "100")
    assert "curad" in (await world.run("/CURAR", user=2)).lower()
    assert await world.redis.hget(key, "min_hp") == "500"
    await world.redis.hset(key, mapping={"min_hp": "0", "death_state": "complete", "life_id": "1"})
    await world.run("/RESUCITAR", user=2)
    assert int(await world.redis.hget(key, "min_hp")) > 0
    assert await world.redis.hget(key, "life_id") == "2"
    assert await world.redis.hget(key, "death_state") == "alive"


@pytest.mark.asyncio
async def test_rest_requires_a_live_fire_and_stops_on_movement(chat_world):
    """Rest requires a live fire and stops on movement."""
    world = chat_world
    assert "fogata" in await world.run("/DESCANSAR", user=2)
    key = RedisKeys.player_user_stats(2)
    assert await world.redis.hget(key, "resting") is None
    await world.redis.hset("world:campfire:2:50:51", mapping={"owner": "2"})
    await world.redis.expire("world:campfire:2:50:51", 60)
    assert "Comienzas" in await world.run("/DESCANSAR", user=2)
    assert await world.redis.hget(key, "resting") == "1"
    await world.redis.hset(RedisKeys.player_position(2), "x", "49")
    await ClassicActionsEffect(world.deps).apply(2, world.deps.player_repo, world.senders[2])
    assert await world.redis.hget(key, "resting") == "0"


@pytest.mark.asyncio
async def test_gambling_and_trainer_are_real_npc_services(chat_world, monkeypatch):
    """Gambling and trainer are real npc services."""
    world = chat_world
    await world.select_npc(104)
    monkeypatch.setattr("src.services.classic_chat.player.secrets.randbelow", lambda _n: 0)
    assert "ganad" in (await world.run("/APOSTAR 100", user=2)).lower()
    assert await world.redis.hget(RedisKeys.player_user_stats(2), "gold") == "1100"
    monkeypatch.setattr("src.services.classic_chat.player.secrets.randbelow", lambda _n: 99)
    assert "perdid" in (await world.run("/APOSTAR 100", user=2)).lower()
    assert await world.redis.hget(RedisKeys.player_user_stats(2), "gold") == "1000"
    await world.select_npc(60, x=53, y=51)
    assert "Entrenamiento" in await world.run("/ENTRENAR", user=2)
    assert "liberado" in await world.run("/ENTRENAR 1", user=2)
    spawned = [npc for npc in world.deps.map_manager.get_npcs_in_map(2) if npc.role == "training"]
    assert len(spawned) == 1
    assert spawned[0].respawn_time == 0
    assert "Ya hay" in await world.run("/ENTRENAR 1", user=2)


@pytest.mark.asyncio
async def test_pet_aliases_preserve_ownership_and_remove_released_pet(chat_world):
    """Pet aliases preserve ownership and remove released pet."""
    world = chat_world
    pet = await world.deps.npc_service.spawn_npc(500, 2, 53, 51)
    pet.is_tamed, pet.summoned_by_user_id = True, 2
    await world.redis.hset(
        RedisKeys.npc_instance(pet.instance_id),
        mapping={"is_tamed": "True", "summoned_by_user_id": "2"},
    )
    await world.redis.sadd("player:2:pets", pet.instance_id)
    await world.run("/QUIETO", user=2)
    assert pet.pet_order == "wait"
    await world.run("/ACOMPAÑAR", user=2)
    assert pet.pet_order == "follow"
    await world.run("/LIBERAR", user=3)
    assert pet.hp > 0  # Otro jugador no puede liberar tus mascotas.
    await world.run("/LIBERAR", user=2)
    assert not await world.redis.exists(RedisKeys.npc_instance(pet.instance_id))
    assert pet not in world.deps.map_manager.get_npcs_in_map(2)


@pytest.mark.asyncio
async def test_faction_rewards_councils_and_bans_preserve_lifetime_counters(chat_world):
    """Faction rewards councils and bans preserve lifetime counters."""
    world = chat_world
    await world.select_npc(72)
    key = RedisKeys.player_user_stats(2)
    assert "actualizada" in await world.run("/ENLISTAR", user=2)
    assert await world.redis.hget(key, "faction_id") == "royal"
    assert "próxima recompensa" in await world.run("/INFORMACION", user=2)
    armor = next(
        identifier for identifier, item in ITEMS_CATALOG.items() if item.item_type.value == "armor"
    )
    await world.run(f"/AI 1 {armor}")
    await world.run(f"/AC 1 {armor}")
    assert await world.redis.hget("faction:armor:royal", "1") == str(armor)
    await world.redis.hset(key, "criminal_kills", "70")
    assert "entregada" in await world.run("/RECOMPENSA", user=2)
    assert await world.redis.hget(key, "faction_reward_royal") == "1"
    bag = await world.redis.hgetall(RedisKeys.player_inventory(2))
    assert any(value for value in bag.values())
    assert "Todavía" in await world.run("/RECOMPENSA", user=2)
    assert await world.redis.hgetall(RedisKeys.player_inventory(2)) == bag
    await world.run("/ACEPTCONSE Jugador")
    assert await world.redis.hget(key, "faction_council") == "1"
    await world.run("/KICKCONSE Jugador")
    assert await world.redis.hget(key, "faction_council") == "0"
    assert "actualizada" in await world.run("/RETIRARFACCION", user=2)
    await world.run("/NOREAL Jugador")
    assert await world.redis.hget(key, "faction_banned_royal") == "1"
    await world.run("/RAJAR Jugador")
    assert await world.redis.hget(key, "criminal_kills") == "70"
    await world.select_npc(98, x=53, y=51)
    assert "actualizada" in await world.run("/ENLISTAR", user=2)
    await world.run("/ACEPTCONSECAOS Jugador")
    assert await world.redis.hget(key, "faction_council") == "1"
    await world.run("/NOCAOS Jugador")
    assert await world.redis.hget(key, "faction_id") == "neutral"


@pytest.mark.asyncio
async def test_classic_party_request_acceptance_and_native_adapters(chat_world):
    """Classic party request acceptance and native adapters."""
    world = chat_world
    await world.redis.hset(RedisKeys.player_skills(2), "level:liderazgo", "100")
    await world.run("/CREARPARTY", user=2)
    party = await world.deps.party_service.get_party_info(2)
    assert party is not None
    await world.redis.hset("chat:target:3", mapping={"user": "2", "map": "2", "npc": ""})
    assert "Solicitud enviada" in await world.run("/PARTY", user=3)
    await world.run("/ACCEPTPARTY Invitado", user=2)
    assert 3 in (await world.deps.party_service.get_party_info(2)).members
    await world.run("/PMSG Mensaje del grupo", user=2)
    assert "Jugador" in await world.run("/ONLINEPARTY", user=3)
    await world.run("/PARTYLIDER Invitado", user=2)
    assert (await world.deps.party_service.get_party_info(3)).is_leader(3)
    await world.run("/ECHARPARTY Jugador", user=3)
    assert await world.deps.party_service.get_party_info(2) is None
    await world.run("/SALIRPARTY", user=3)
    assert await world.deps.party_service.get_party_info(3) is None


@pytest.mark.asyncio
async def test_home_deadline_survives_reconnection_and_jail_blocks_escape(chat_world):
    """Home deadline survives reconnection and jail blocks escape."""
    world = chat_world
    key = RedisKeys.player_user_stats(2)
    await world.redis.hset(RedisKeys.home_spawn(1), mapping={"map": "1", "x": "40", "y": "40"})
    await world.redis.hset(key, mapping={"min_hp": "0", "death_state": "complete", "life_id": "1"})
    assert "60 segundos" in await world.run("/HOGAR", user=2)
    assert float(await world.redis.hget(key, "home_due")) > time.time()
    assert "cancelado" in await world.run("/HOGAR", user=2)
    assert await world.redis.hget(key, "home_due") == "0"
    await world.run("/HOGAR", user=2)
    await world.redis.hset(key, "home_due", str(time.time() - 1))
    await ClassicActionsEffect(world.deps).apply(2, world.deps.player_repo, world.senders[2])
    assert (await world.deps.player_repo.get_position(2))["map"] == 1
    assert await world.redis.hget(key, "home_due") == "0"
