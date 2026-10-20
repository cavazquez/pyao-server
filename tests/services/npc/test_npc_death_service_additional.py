"""Veneno y devaluación de recompensas, con Redis y transacciones concretas."""

import asyncio
import time
from types import SimpleNamespace

import pytest

from src.economy.taxes import TAX_POLICY_KEY, utc_day
from src.effects.effect_npc_poison import NPCPoisonEffect
from src.services.npc.rewards.poison import poison_tick
from src.utils.redis_config import RedisKeys
from tests.services.npc.test_npc_death_service import ground


@pytest.mark.asyncio
async def test_npc_poison_uses_common_rewards_and_counts_once(rewards):
    """El veneno letal liquida el botín y el contador una sola vez."""
    npc = await rewards.spawn(hp=5)
    npc.poisoned_until = time.time() + 100
    npc.poisoned_by_user_id = 1
    await rewards.npcs.update_npc_poisoned_until(npc.instance_id, npc.poisoned_until, 1)
    effect = NPCPoisonEffect(
        SimpleNamespace(npc_repository=rewards.npcs), npc_death_service=rewards.service
    )
    await asyncio.gather(*(effect._process_poisoned_npc(npc, time.time()) for _ in range(2)))
    assert await rewards.npcs.get_npc(npc.instance_id) is None
    assert await rewards.client.hget(RedisKeys.player_user_stats(1), "npc_kills") == "1"
    assert (await rewards.player.get_experience(1))[0] == 200
    assert sorted((r["item_id"], r["quantity"]) for r in await ground(rewards)) == [
        (12, 20),
        (15, 1),
    ]


@pytest.mark.asyncio
async def test_poison_interval_and_stale_dose_do_not_overwrite_hp(rewards):
    """Una dosis nueva y los intervalos bloquean aplicaciones repetidas."""
    npc = await rewards.spawn(hp=20)
    now = time.time()
    npc.poisoned_until = now + 100
    npc.poisoned_by_user_id = 1
    await rewards.npcs.update_npc_poisoned_until(npc.instance_id, npc.poisoned_until, 1)
    await asyncio.gather(*(poison_tick(rewards.client.redis, npc, now, 2) for _ in range(2)))
    assert (await rewards.npcs.get_npc(npc.instance_id)).hp == 15
    assert not (await poison_tick(rewards.client.redis, npc, now + 1, 2))["applied"]
    assert (await poison_tick(rewards.client.redis, npc, now + 2, 2))["new_hp"] == 10
    await rewards.npcs.update_npc_poisoned_until(npc.instance_id, now + 200, 2)
    assert not (await poison_tick(rewards.client.redis, npc, now + 4, 2))["applied"]
    assert (await rewards.npcs.get_npc(npc.instance_id)).hp == 10


@pytest.mark.asyncio
async def test_expired_poison_does_not_kill_or_reward(rewards):
    """El vencimiento del veneno no causa un golpe letal ni incrementa muertes."""
    npc = await rewards.spawn(hp=5)
    npc.poisoned_until = time.time() - 1
    npc.poisoned_by_user_id = 1
    await rewards.npcs.update_npc_poisoned_until(npc.instance_id, npc.poisoned_until, 1)
    result = await poison_tick(rewards.client.redis, npc, time.time(), 2)
    assert not result["died"]
    assert (await rewards.npcs.get_npc(npc.instance_id)).hp == 5
    assert await rewards.client.hget(RedisKeys.player_user_stats(1), "npc_kills") is None


@pytest.mark.asyncio
async def test_pending_gold_keeps_its_devaluation_clock(rewards, monkeypatch):
    """Esperar la liquidación no rejuvenece el oro de una muerte anterior."""
    day = utc_day()
    await rewards.client.hset(
        TAX_POLICY_KEY,
        mapping={
            "version": "1",
            "activation_day": str(day - 2),
            "ground_activation_day": str(day - 2),
            "enabled": "1",
            "rate_bps": "100",
        },
    )
    monkeypatch.setattr(rewards.service.loot_table_service, "roll", lambda _npc: [(12, 1000)])
    npc = await rewards.spawn()
    await rewards.client.hset(
        RedisKeys.npc_instance(npc.instance_id), "death_at", str(time.time() - 86400)
    )
    await rewards.service.handle_npc_death(npc, 1, 50, None)
    gold = next(r for r in await ground(rewards) if r["item_id"] == 12)
    assert gold["quantity"] == 990
    assert gold["devaluation_day"] == day
    assert gold["devaluation_remainder"] == 0
