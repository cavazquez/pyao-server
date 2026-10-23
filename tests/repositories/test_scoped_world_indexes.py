"""Consultas acotadas, membresías atómicas y reconstrucción sin pisar partidas."""

import asyncio
import os
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio

from src.config.game_config import RedisConfig
from src.effects.effect_pet_follow import PetFollowEffect
from src.game.map_manager import MapManager
from src.operations.redis_sandbox import RedisSandbox, docker
from src.repositories.campfire_repository import CampfireRepository, campfire_index
from src.repositories.npc_repository import NPCRepository
from src.repositories.player_repository import PlayerRepository
from src.services.npc.summon_service import SummonService
from src.utils.gold_atomic import operation_id
from src.utils.pet_index import owner_key
from src.utils.redis_config import RedisKeys
from src.utils.resource_transaction import Decision, Resource, transact


@pytest.fixture(scope="module")
def isolated_store():
    """Redis real sólo por opción explícita.

    Yields:
        Contenedor/volumen propios, o None para el backend en memoria.
    """
    if os.environ.get("PYAO_RUN_SCOPED_INDEX_REDIS") != "1":
        yield None
        return
    with RedisSandbox() as sandbox:
        yield sandbox


@pytest_asyncio.fixture
async def index_redis(redis_client, isolated_store):
    """Reutiliza las mismas pruebas con backend fake o Redis/AOF aislado.

    Yields:
        Cliente exclusivo del backend seleccionado.
    """
    if isolated_store is None:
        yield redis_client
        return
    await redis_client.redis.aclose()
    redis_client._redis = None
    await redis_client.connect(
        RedisConfig(
            host="127.0.0.1", port=isolated_store.port, password_file=isolated_store.password_file
        ),
        seed_defaults=False,
    )
    await redis_client.redis.flushdb()  # Este cliente sólo apunta al sandbox recién creado.
    try:
        yield redis_client
    finally:
        await redis_client.disconnect()


async def create_pet(repo, owner=1, *, permanent=False, expires=None):
    """Instancia completa y autoritativa, sin falsificar el índice a probar."""
    return await repo.create_npc_instance(
        1,
        10001 + owner,
        1,
        50,
        50,
        3,
        "Pet",
        "",
        1,
        0,
        100,
        100,
        1,
        False,
        True,
        0,
        0,
        0,
        0,
        summoned_by_user_id=owner,
        summoned_until=(time.time() + 600 if expires is None else expires) if not permanent else 0,
        is_tamed=permanent,
    )


@pytest.mark.asyncio
async def test_owner_index_excludes_others_dead_expired_and_administrative_followers(index_redis):
    """No usa descubrimiento global ni acredita un seguidor GM como mascota."""
    repo = NPCRepository(index_redis)
    pet = await create_pet(repo)
    other = await create_pet(repo, 2)
    expired = await create_pet(repo, 1, expires=1)
    dead = await create_pet(repo)
    await repo.update_npc_hp(dead.instance_id, 0)
    follower = await create_pet(repo, 0, expires=0)
    await index_redis.hset(RedisKeys.npc_instance(follower.instance_id), "gm_follow_user", "1")
    await index_redis.sadd(owner_key(1), other.instance_id, follower.instance_id, "missing")
    with (
        patch.object(index_redis, "keys", side_effect=AssertionError("KEYS global")),
        patch.object(index_redis.redis, "scan_iter", side_effect=AssertionError("SCAN global")),
    ):
        assert [n.instance_id for n in await repo.get_player_pets(1)] == [pet.instance_id]
        assert {n.instance_id for n in await repo.get_player_pets(1, include_expired=True)} == {
            pet.instance_id,
            expired.instance_id,
        }
    assert await index_redis.smembers(owner_key(1)) == {pet.instance_id, expired.instance_id}
    assert await repo.get_npc(other.instance_id) is not None
    assert await repo.get_npc(follower.instance_id) is not None


@pytest.mark.asyncio
async def test_owner_change_death_and_removal_update_only_affected_memberships(index_redis):
    """El cambio de dueño no deja autoridad anterior ni borra a otro jugador."""
    repo = NPCRepository(index_redis)
    pet, other = await create_pet(repo), await create_pet(repo, 2)
    await repo.update_npc_summoned(pet.instance_id, 2, time.time() + 600)
    assert await repo.get_player_pets(1) == []
    assert await index_redis.smembers(owner_key(2)) == {pet.instance_id, other.instance_id}
    await repo.update_npc_hp(pet.instance_id, 0)
    assert await index_redis.smembers(owner_key(2)) == {other.instance_id}
    await repo.remove_npc(pet.instance_id)
    assert await repo.get_npc(pet.instance_id) is None
    assert await index_redis.smembers(owner_key(2)) == {other.instance_id}


@pytest.mark.asyncio
async def test_transaction_receipt_and_membership_share_commit(index_redis):
    """Perder un ACK y repetir no duplica mascotas; muerte quita su referencia."""
    repo = NPCRepository(index_redis)
    pet = await create_pet(repo, 0, expires=0)
    key, identity = RedisKeys.npc_instance(pet.instance_id), operation_id()
    changes = {"summoned_by_user_id": "1", "is_tamed": "True"}
    for _ in range(2):
        result = await transact(
            index_redis.redis,
            (Resource(key, "hash"),),
            identity,
            {"adopt": pet.instance_id},
            lambda _: Decision({"applied": True}, {key: changes}),
        )
        assert result["applied"]
    assert await index_redis.smembers(owner_key(1)) == {pet.instance_id}
    await transact(
        index_redis.redis,
        (Resource(key, "hash"),),
        operation_id(),
        {"kill": pet.instance_id},
        lambda _: Decision({"applied": True}, {key: {"hp": "0"}}),
    )
    assert await index_redis.smembers(owner_key(1)) == set()


@pytest.mark.asyncio
async def test_restart_rebuilds_owners_and_maps_preserving_only_living_tamed_pets(index_redis):
    """Un Redis nuevo y otro con datos se recuperan sin duplicar ni pisar cuentas."""
    repo = NPCRepository(index_redis)
    await repo.clear_all_npcs(preserve_tamed=True)
    pet, other = await create_pet(repo, permanent=True), await create_pet(repo, 2, permanent=True)
    transient = await create_pet(repo)
    await index_redis.sadd(owner_key(999), "stale")
    await index_redis.set("account:unrelated", "preserve")
    for _ in range(2):
        await repo.clear_all_npcs(preserve_tamed=True)
        assert [n.instance_id for n in await repo.get_player_pets(1)] == [pet.instance_id]
        assert [n.instance_id for n in await repo.get_player_pets(2)] == [other.instance_id]
        assert await index_redis.smembers(owner_key(999)) == set()
        assert await index_redis.smembers(RedisKeys.npc_map_index(1)) == {
            pet.instance_id,
            other.instance_id,
        }
        assert await index_redis.get("account:unrelated") == "preserve"
        assert await repo.get_npc(transient.instance_id) is None


@pytest.mark.asyncio
async def test_disconnect_keeps_permanent_and_other_owners_even_with_expired_summon(index_redis):
    """La limpieza toma sólo las invocaciones temporales de ese dueño."""
    repo = NPCRepository(index_redis)
    permanent = await create_pet(repo, permanent=True)
    transient = await create_pet(repo, expires=1)
    other = await create_pet(repo, 2)
    service = SummonService(repo, PlayerRepository(index_redis))
    assert await service.remove_all_player_pets(1) == [transient.instance_id]
    assert await service.get_player_pets(1) == [permanent.instance_id]
    assert await service.get_player_pets(2) == [other.instance_id]


@pytest.mark.asyncio
async def test_local_pet_index_rebinds_mutable_owner_map_and_removal(index_redis):
    """Seguimiento/snapshot usan índices locales; cambiar de mapa no duplica."""
    repo, maps = NPCRepository(index_redis), MapManager()
    pet = await create_pet(repo, permanent=True)
    maps.add_npc(1, pet)
    assert maps.get_player_pets(1) == [pet]
    assert maps.get_npc_by_instance(pet.instance_id) is pet
    pet.map_id, pet.summoned_by_user_id = 2, 2
    maps.add_npc(2, pet)
    assert maps.get_player_pets(1) == []
    assert maps.get_player_pets(2) == [pet]
    assert maps.get_all_pets() == [pet]
    maps.remove_npc(2, pet.instance_id)
    assert maps.get_all_pets() == []
    assert maps.get_npc_by_instance(pet.instance_id) is None


@pytest.mark.asyncio
async def test_concurrent_owner_updates_do_not_duplicate_membership(index_redis):
    """WATCH confirma cada actualización y el último dueño es el único indexado."""
    repo = NPCRepository(index_redis)
    pet = await create_pet(repo)
    await asyncio.gather(
        *(
            repo.update_npc_summoned(pet.instance_id, owner, time.time() + 600)
            for owner in (2, 3, 4, 5)
        )
    )
    saved = await repo.get_npc(pet.instance_id)
    assert saved is not None
    for owner in range(1, 6):
        assert await index_redis.smembers(owner_key(owner)) == (
            {pet.instance_id} if owner == saved.summoned_by_user_id else set()
        )


@pytest.mark.asyncio
async def test_follow_uses_local_pet_index_without_npc_redis_reads(index_redis):
    """El tick no recorre NPC ajenos ni Redis para descubrir las mascotas."""
    repo, maps = NPCRepository(index_redis), MapManager()
    pet = await create_pet(repo)
    maps.add_npc(pet.map_id, pet)
    maps.add_player(1, 1, object(), "Owner")
    players = PlayerRepository(index_redis)
    await players.set_position(1, 60, 50, 1, 3)
    await index_redis.hset(RedisKeys.player_user_stats(1), mapping={"min_hp": "100"})
    effect = PetFollowEffect(
        SimpleNamespace(map_manager=maps, npc_repository=repo), interval_seconds=0
    )
    with (
        patch.object(repo, "get_all_npcs", side_effect=AssertionError("global NPC scan")),
        patch.object(repo, "get_player_pets", side_effect=AssertionError("Redis pet discovery")),
        patch.object(effect, "_move_pet_towards_owner", new=AsyncMock()) as move,
    ):
        await effect.apply(1, players, None)
        move.assert_awaited_once()
        pet.hp = 0
        await effect.apply(1, players, None)
        move.assert_awaited_once()


@pytest.mark.asyncio
async def test_stale_owner_pruning_does_not_erase_a_reassigned_back_pet(index_redis):
    """La instancia pudo cambiar después del lote; se vuelve a validar bajo WATCH."""
    repo = NPCRepository(index_redis)
    pet = await create_pet(repo)
    # Simula la ventana entre la respuesta del lote y su limpieza diferida.
    await repo._prune_owner_index(1, [pet.instance_id])
    assert await index_redis.smembers(owner_key(1)) == {pet.instance_id}


@pytest.mark.asyncio
async def test_campfire_pruning_does_not_erase_a_recreated_fire(index_redis):
    """Una referencia considerada obsoleta sigue presente si la fogata volvió a vivir."""
    repo = CampfireRepository(index_redis)
    key, now = "world:campfire:1:50:50", time.time()
    await index_redis.hset(key, mapping={"until": str(now + 120), "x": "50", "y": "50"})
    await index_redis.sadd(campfire_index(1), key)
    await repo._prune(1, {key}, now)
    assert await index_redis.smembers(campfire_index(1)) == {key}


@pytest.mark.asyncio
async def test_campfire_index_prunes_expired_missing_and_foreign_without_global_scan(index_redis):
    """MATCH no forma parte de una lectura de juego; referencias ajenas no se borran."""
    repo = CampfireRepository(index_redis)
    now = time.time()
    current, expired, missing, foreign = (
        "world:campfire:1:50:50",
        "world:campfire:1:51:50",
        "world:campfire:1:52:50",
        "world:campfire:2:50:50",
    )
    for key, until, x in (
        (current, now + 120, 50),
        (expired, now - 1, 51),
        (foreign, now + 120, 50),
    ):
        await index_redis.hset(key, mapping={"until": str(until), "x": str(x), "y": "50"})
    await index_redis.sadd(campfire_index(1), current, expired, missing, foreign)
    await index_redis.sadd(campfire_index(2), foreign)
    with patch.object(index_redis.redis, "scan_iter", side_effect=AssertionError("SCAN global")):
        assert await repo.positions(1, now) == {(50, 50)}
    assert await index_redis.smembers(campfire_index(1)) == {current}
    assert await index_redis.smembers(campfire_index(2)) == {foreign}
    assert await index_redis.hgetall(foreign)
    await repo.remove(1, 50, 50)
    assert await repo.positions(1, now) == set()
    assert await index_redis.hgetall(foreign)


@pytest.mark.asyncio
async def test_campfire_restart_recovers_hashes_and_preserves_ttls(index_redis):
    """La reconstrucción inicial es idempotente y no renueva la duración."""
    repo = CampfireRepository(index_redis)
    key = "world:campfire:1:50:50"
    await repo.rebuild()
    await index_redis.hset(key, mapping={"until": str(time.time() + 120), "x": "50", "y": "50"})
    await index_redis.redis.expire(key, 90)
    before = await index_redis.redis.ttl(key)
    await index_redis.sadd(campfire_index(999), "stale")
    for _ in range(2):
        await repo.rebuild()
        assert await repo.positions(1, time.time()) == {(50, 50)}
        assert 0 < await index_redis.redis.ttl(key) <= before
        assert await index_redis.smembers(campfire_index(999)) == set()


@pytest.mark.asyncio
async def test_indices_survive_real_redis_aof_restart(index_redis, isolated_store):
    """Un reinicio del proceso Redis conserva instancias e índices, sin renovar fogatas."""
    if isolated_store is None:
        pytest.skip("Enable PYAO_RUN_SCOPED_INDEX_REDIS=1 for the owned Redis/AOF test")
    npcs, fires = NPCRepository(index_redis), CampfireRepository(index_redis)
    pet = await create_pet(npcs, permanent=True)
    key = "world:campfire:1:50:50"
    await index_redis.hset(key, mapping={"until": str(time.time() + 120), "x": "50", "y": "50"})
    await index_redis.redis.expire(key, 120)
    await fires.rebuild()
    await index_redis.redis.save()
    await asyncio.to_thread(docker, "restart", isolated_store.name)
    await asyncio.to_thread(lambda: isolated_store.client().close())
    await index_redis.disconnect()
    await index_redis.connect(
        RedisConfig(
            host="127.0.0.1", port=isolated_store.port, password_file=isolated_store.password_file
        ),
        seed_defaults=False,
    )
    await fires.rebuild()
    await npcs.clear_all_npcs(preserve_tamed=True)
    assert [row.instance_id for row in await npcs.get_player_pets(1)] == [pet.instance_id]
    assert await fires.positions(1, time.time()) == {(50, 50)}
    assert 0 < await index_redis.redis.ttl(key) <= 120
