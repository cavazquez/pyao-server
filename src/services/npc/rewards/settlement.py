"""Botín, experiencia y recibo de una muerte de NPC confirmados en un solo EXEC."""

import json
import time
from typing import TYPE_CHECKING, Any, cast

from src.economy.taxes import TAX_POLICY_KEY, assess_tax, utc_day
from src.models.item_constants import GOLD_ITEM_ID
from src.services.npc.rewards.plan import (
    RewardContext,
    RewardContextChangedError,
    award_changes,
    experience_plan,
    reward_context,
)
from src.utils.durability import require_durable
from src.utils.gold_atomic import operation_id
from src.utils.ground_state import (
    GROUND_TTL_SECONDS,
    MAX_GROUND_ITEMS_PER_TILE,
    GroundItem,
    GroundState,
    stack_identity,
)
from src.utils.redis_config import RedisKeys
from src.utils.resource_transaction import Decision, Resource, Snapshot, transact

if TYPE_CHECKING:
    from redis.asyncio import Redis

    from src.models.npc import NPC
    from src.services.npc.loot_table_service import LootTableService

REWARD_RECEIPT_SECONDS = 86400
MAX_REWARD_CONTEXT_ATTEMPTS = 4


def death_changes(hp: int, killer: int, *, now: float | None = None) -> dict[str, str]:
    """Marca daño letal de NPC junto al HP para recuperar una caída antes del handler.

    Returns:
        Campos exactos de la instancia; no genera botín en memoria.
    """
    changes = {"hp": str(hp)}
    if hp <= 0:
        changes.update(
            death_state="pending",
            death_killer=str(killer),
            death_at=str(time.time() if now is None else now),
        )
    return changes


def _ground_items(
    npc: NPC, plan: dict[str, Any], policy: dict[str, str], loot: LootTableService
) -> list[GroundItem]:
    items: list[GroundItem] = []
    for index, (item_id, quantity) in enumerate(plan["items"]):
        item: GroundItem = {
            "item_id": item_id,
            "quantity": quantity,
            "grh_index": loot.catalog.get_grh_index(item_id) or 0,
            "stack_id": stack_identity(f"npc:{npc.instance_id}:loot:{index}"),
            "owner_id": None,
        }
        if item_id == GOLD_ITEM_ID:
            today = utc_day()
            activation = int(policy.get("ground_activation_day", plan["created_day"]))
            tax = assess_tax(
                quantity,
                0,
                max(activation, int(plan["created_day"])),
                today,
                rate_bps=int(policy.get("rate_bps", 100)) if policy.get("enabled") == "1" else 0,
            )
            item.update(
                quantity=tax.wallet,
                devaluation_day=tax.last_day,
                devaluation_remainder=tax.remainder,
            )
        if int(item["quantity"] or 0) > 0:
            items.append(item)
    return items


async def settle_rewards(
    redis: Redis,
    npc: NPC,
    killer: int,
    experience: int,
    loot: LootTableService,
    positions: tuple[tuple[int, int], ...],
) -> dict[str, Any]:
    """Reutiliza el plan pendiente, nunca tira dados ni paga otra vez una muerte resuelta.

    Returns:
        Commit único, pendiente por capacidad o rechazo de instancia viva/retirada.

    Raises:
        RuntimeError: Si una party cambia continuamente e impide congelar destinatarios.
    """
    npc_key, ground_key = (
        RedisKeys.npc_instance(npc.instance_id),
        RedisKeys.ground_items(npc.map_id),
    )
    receipt_key = f"npc:death:{npc.instance_id}"
    proposed = loot.roll(npc)
    for _ in range(MAX_REWARD_CONTEXT_ATTEMPTS):
        preview = await redis.hgetall(npc_key)
        saved = preview.get("reward_plan")
        context = await reward_context(
            redis, killer, saved.decode() if isinstance(saved, bytes) else saved
        )
        resources = (
            Resource(npc_key, "hash"),
            Resource(ground_key, "string", GROUND_TTL_SECONDS),
            Resource(receipt_key, "string", REWARD_RECEIPT_SECONDS),
            *context.resources,
        )

        def decide(snapshot: Snapshot, context: RewardContext = context) -> Decision:
            state = cast("dict[str, str]", snapshot[npc_key])
            if not state or int(state.get("hp", 1)) > 0:
                return Decision({"applied": False, "settled": False}, {})
            if state.get("death_state") == "complete":
                return Decision({"applied": False, "settled": True}, {})
            if state.get("reward_plan"):
                plan = json.loads(state["reward_plan"])
            else:
                plan = {
                    **experience_plan(
                        snapshot,
                        context,
                        0 if npc.is_tamed or npc.summoned_by_user_id else max(0, experience),
                        npc.map_id,
                        npc.x,
                        npc.y,
                    ),
                    "items": proposed,
                    "version": 2,
                    "created_day": utc_day(float(state.get("death_at", time.time()))),
                }
            ground = GroundState(npc.map_id, cast("str | None", snapshot[ground_key]))
            changed: set[tuple[int, int]] = set()
            items = _ground_items(
                npc, plan, cast("dict[str, str]", snapshot.get(TAX_POLICY_KEY) or {}), loot
            )
            for item in items:
                available = next(
                    (
                        position
                        for position in positions
                        if len(ground.tile(*position)) < MAX_GROUND_ITEMS_PER_TILE
                    ),
                    None,
                )
                if available is None:
                    return Decision(
                        {"applied": False, "settled": False, "pending": True},
                        {
                            npc_key: {
                                "death_state": "pending",
                                "death_killer": str(killer),
                                "reward_plan": json.dumps(plan),
                            }
                        },
                    )
                ground.append(*available, item)
                changed.add(available)
            writes, levels = award_changes(snapshot, context, plan)
            result = {
                "applied": True,
                "settled": True,
                "levels": levels,
                "ground_positions": sorted(changed),
                "items": items,
                "party_id": plan["party_id"],
                "total_exp": plan["total_exp"],
            }
            writes.update(
                {
                    npc_key: {"death_state": "complete", "reward_plan": json.dumps(plan)},
                    receipt_key: json.dumps(
                        {"version": 2, "npc_id": npc.npc_id, "level": npc.level, "result": result}
                    ),
                }
            )
            if items:
                writes[ground_key] = ground.encode()
            return Decision(result, writes)

        try:
            await require_durable(redis)
            result = await transact(
                redis,
                resources,
                operation_id(),
                {"npc_death": npc.instance_id, "killer": killer},
                decide,
            )
            await require_durable(redis)
        except RewardContextChangedError:
            continue
        else:
            return result
    message = "Cambió la party durante la muerte del NPC; se conserva para reintentar"
    raise RuntimeError(message)
