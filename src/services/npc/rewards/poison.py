"""Pulso relativo de veneno: HP, atribución y muerte pendiente comparten commit."""

from typing import TYPE_CHECKING, Any, cast

from src.services.npc.rewards.settlement import death_changes
from src.services.player.lifetime_stats import kill_changes
from src.utils.gold_atomic import operation_id
from src.utils.redis_config import RedisKeys
from src.utils.resource_transaction import Decision, Resource, Snapshot, transact

if TYPE_CHECKING:
    from redis.asyncio import Redis

    from src.models.npc import NPC


async def poison_tick(redis: Redis, npc: NPC, now: float, interval: float) -> dict[str, Any]:
    """Un tick viejo no pisa HP ni una dosis nueva; dos workers no duplican daño/bajas.

    Returns:
        HP confirmado y emisor de una transición letal real.
    """
    key = RedisKeys.npc_instance(npc.instance_id)
    user = npc.poisoned_by_user_id
    user_key = RedisKeys.player_user_stats(user)
    resources = (Resource(key, "hash"), *((Resource(user_key, "hash"),) if user > 0 else ()))

    def decide(snapshot: Snapshot) -> Decision:
        state = cast("dict[str, str]", snapshot[key])
        hp = int(state.get("hp", 0))
        result = {"applied": False, "new_hp": hp, "died": False, "killer": user}
        if (
            not state
            or hp <= 0
            or float(state.get("poisoned_until", 0)) != npc.poisoned_until  # ruff: ignore[float-equality-comparison] - identidad exacta de dosis, no tolerancia temporal.
            or int(state.get("poisoned_by_user_id", 0)) != user
        ):
            return Decision(result, {})
        if now >= npc.poisoned_until:
            return Decision(result, {key: {"poisoned_until": "0", "poisoned_by_user_id": "0"}})
        if now < float(state.get("poison_next_tick", 0)):
            return Decision(result, {})
        new_hp = max(0, hp - 5)
        writes: dict[str, str | dict[str, str] | set[str]] = {
            key: {**death_changes(new_hp, user, now=now), "poison_next_tick": str(now + interval)}
        }
        if new_hp == 0 and user > 0 and snapshot[user_key]:
            writes[user_key] = kill_changes(
                cast("dict[str, str]", snapshot[user_key]), state, player=False
            )
        return Decision({**result, "applied": True, "new_hp": new_hp, "died": new_hp == 0}, writes)

    return await transact(
        redis, resources, operation_id(), {"npc_poison": npc.instance_id, "time": now}, decide
    )
