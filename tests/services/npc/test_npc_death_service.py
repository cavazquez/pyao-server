"""Recompensas reales sobre Redis: un commit por muerte, no mocks de oro o experiencia."""

import asyncio
import json
from unittest.mock import AsyncMock

import pytest

from src.models.party import Party
from src.repositories.party_repository import PartyRepository
from src.utils.ground_state import GroundState, stack_identity
from src.utils.redis_config import RedisKeys


async def ground(world):
    """Lee el formato durable sin depender de la caché del servicio."""
    state = GroundState(2, await world.client.get(RedisKeys.ground_items(2)))
    return [item for rows in state.tiles.values() for item in rows]


@pytest.mark.asyncio
async def test_concurrent_duplicate_death_does_not_duplicate_rewards(rewards):
    """Tres avisos de una muerte emiten una sola recompensa y un solo respawn."""
    npc = await rewards.spawn()
    await asyncio.gather(
        *(rewards.service.handle_npc_death(npc, 1, 50, rewards.senders[1]) for _ in range(3))
    )
    assert await rewards.player.get_experience(1) == (
        150,
        int(await rewards.client.hget(RedisKeys.player_user_stats(1), "elu")),
    )
    assert sorted((r["item_id"], r["quantity"]) for r in await ground(rewards)) == [
        (12, 20),
        (15, 1),
    ]
    assert await rewards.npcs.get_npc(npc.instance_id) is None
    rewards.respawn.schedule_respawn.assert_awaited_once()
    rewards.random_spawn.on_random_npc_death.assert_awaited_once_with(npc.instance_id)
    assert await rewards.client.redis.ttl(f"npc:death:{npc.instance_id}") > 0
    # Ni el oro del viejo campo del NPC ni el saldo del atacante se acreditan aparte.
    assert await rewards.player.get_gold(1) == 0


@pytest.mark.asyncio
async def test_two_npcs_award_relative_experience_without_lost_update(rewards):
    """Muertes concurrentes conservan ambas sumas de experiencia y botín."""
    first, second = await rewards.spawn(), await rewards.spawn(x=55)
    await asyncio.gather(
        *(rewards.service.handle_npc_death(npc, 1, 50, None) for npc in (first, second))
    )
    assert (await rewards.player.get_experience(1))[0] == 200
    items = await ground(rewards)
    assert sum(int(r["quantity"]) for r in items if r["item_id"] == 12) == 40
    assert len({r["stack_id"] for r in items}) == 4


@pytest.mark.asyncio
@pytest.mark.parametrize("excluded", ["far", "offline", "dead", "other_map"])
async def test_party_formula_and_accounting_share_the_commit(rewards, excluded):
    """La distancia y el estado filtran miembros sin duplicar el libro de la party."""
    party = Party(1, 1, "user1")
    party.update_member_level(1, 10)
    for user in (2, 3):
        party.add_member(user, f"user{user}", 10)
    if excluded == "offline":
        party.members[3].is_online = False
    elif excluded == "dead":
        await rewards.client.hset(RedisKeys.player_user_stats(3), "min_hp", "0")
    else:
        await rewards.player.set_position(3, 90, 90, 3 if excluded == "other_map" else 2, 3)
    await PartyRepository(rewards.client).save_party(party)
    npc = await rewards.spawn()
    await rewards.service.handle_npc_death(npc, 1, 50, rewards.senders[1])
    for user in (1, 2):
        assert (await rewards.player.get_experience(user))[0] == 116
    assert (await rewards.player.get_experience(3))[0] == 100
    saved = await PartyRepository(rewards.client).get_party(1)
    assert saved.total_exp_earned == 50
    assert saved.members[1].accumulated_exp == 16
    assert saved.members[2].accumulated_exp == 16
    assert saved.members[3].accumulated_exp == 0
    await rewards.service.handle_npc_death(npc, 1, 50, None)
    assert (await PartyRepository(rewards.client).get_party(1)).total_exp_earned == 50


@pytest.mark.asyncio
async def test_pending_full_ground_rolls_back_every_drop_and_xp(rewards, monkeypatch):
    """Un suelo lleno conserva el plan hasta poder publicarlo completo."""
    npc = await rewards.spawn()
    monkeypatch.setattr(rewards.service, "_drop_positions", lambda _npc: ((49, 49),))
    state = GroundState(2, None)
    for index in range(9):
        state.append(
            49, 49, {"item_id": 1, "quantity": 1, "stack_id": stack_identity(f"occupied:{index}")}
        )
    original = state.encode()
    await rewards.client.set(RedisKeys.ground_items(2), original)
    await rewards.service.handle_npc_death(npc, 1, 50, None)
    assert await rewards.client.get(RedisKeys.ground_items(2)) == original
    assert (await rewards.player.get_experience(1))[0] == 100
    raw = await rewards.client.hgetall(RedisKeys.npc_instance(npc.instance_id))
    assert raw["death_state"] == "pending"
    frozen = json.loads(raw["reward_plan"])
    await rewards.npcs.clear_all_npcs(preserve_tamed=True)
    assert await rewards.npcs.get_npc(npc.instance_id) is not None
    await rewards.client.delete(RedisKeys.ground_items(2))
    rewards.maps.remove_player(2, 1)  # El atacante se desconectó; no se pierde su recompensa.
    await rewards.service.recover_pending(all_records=True, bootstrap=True)
    assert sorted((r["item_id"], r["quantity"]) for r in await ground(rewards)) == sorted(
        map(tuple, frozen["items"])
    )
    assert (await rewards.player.get_experience(1))[0] == 150
    rewards.respawn.schedule_respawn.assert_not_awaited()


@pytest.mark.asyncio
async def test_crash_after_commit_recovers_without_second_reward(rewards, monkeypatch):
    """Recuperar un cadáver confirmado no vuelve a pagar aunque falte el recibo."""
    npc = await rewards.spawn()
    remove = rewards.service._remove_npc_from_game
    monkeypatch.setattr(
        rewards.service, "_remove_npc_from_game", AsyncMock(side_effect=ConnectionError("fixture"))
    )
    with pytest.raises(ConnectionError):
        await rewards.service.handle_npc_death(npc, 1, 50, None)
    before = await ground(rewards)
    assert (await rewards.player.get_experience(1))[0] == 150
    monkeypatch.setattr(rewards.service, "_remove_npc_from_game", remove)
    await rewards.service.recover_pending(all_records=True)
    assert await ground(rewards) == before
    assert (await rewards.player.get_experience(1))[0] == 150
    # Aun sin recibo temporal o suelo, una referencia vieja no representa una nueva vida.
    await rewards.client.delete(f"npc:death:{npc.instance_id}", RedisKeys.ground_items(2))
    await rewards.service.handle_npc_death(npc, 1, 50, None)
    assert await ground(rewards) == []
    assert (await rewards.player.get_experience(1))[0] == 150


@pytest.mark.asyncio
async def test_live_npc_cannot_be_settled(rewards):
    """Un objeto NPC obsoleto no permite cobrar una instancia que sigue viva."""
    npc = await rewards.spawn(hp=1)
    await rewards.service.handle_npc_death(npc, 1, 50, None)
    assert await rewards.npcs.get_npc(npc.instance_id) is not None
    assert await ground(rewards) == []
    assert (await rewards.player.get_experience(1))[0] == 100


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["tamed", "summoned"])
async def test_owned_creatures_cannot_farm_loot_or_experience(rewards, kind):
    """Las mascotas e invocaciones no producen recompensas de combate."""
    npc = await rewards.spawn(tamed=kind == "tamed", summoned=1 if kind == "summoned" else 0)
    await rewards.service.handle_npc_death(npc, 1, 500, None)
    assert await ground(rewards) == []
    assert (await rewards.player.get_experience(1))[0] == 100


@pytest.mark.asyncio
async def test_level_points_are_awarded_with_xp_once(rewards):
    """El mismo commit acredita experiencia, niveles y puntos una sola vez."""
    await rewards.client.hset(
        RedisKeys.player_user_stats(1), mapping={"experience": "0", "level": "1"}
    )
    await rewards.client.hset(
        RedisKeys.player_skills(1), mapping={"points": "0", "points_granted_through": "1"}
    )
    npc = await rewards.spawn()
    await rewards.service.handle_npc_death(npc, 1, 5000, None)
    after = await rewards.client.hgetall(RedisKeys.player_skills(1))
    assert int(after["points"]) > 0
    assert await rewards.player.get_level(1) > 1
    await rewards.service.handle_npc_death(npc, 1, 5000, None)
    assert await rewards.client.hgetall(RedisKeys.player_skills(1)) == after


@pytest.mark.asyncio
async def test_ground_notifications_cover_actual_drop_positions(rewards):
    """Los clientes reciben las casillas reales que ocupan los objetos."""
    npc = await rewards.spawn()
    await rewards.service.handle_npc_death(npc, 1, 50, None)
    raw = GroundState(2, await rewards.client.get(RedisKeys.ground_items(2)))
    assert set(raw.positions()) - {(npc.x, npc.y)}
    called = {
        (c.kwargs["x"], c.kwargs["y"])
        for c in rewards.broadcast.broadcast_object_create.await_args_list
    }
    assert set(raw.positions()).issubset(called)
