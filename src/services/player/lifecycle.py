"""Generaciones de vida: daño, liquidación de muerte y resurrección sin duplicación."""

import random
import time
from typing import TYPE_CHECKING, Any, cast

from src.config.config_manager import config_manager
from src.economy.ground_devaluation import split_remainder
from src.economy.tax_transactions import tax_key
from src.models.item_constants import GOLD_ITEM_ID
from src.models.items_catalog import ITEMS_CATALOG
from src.services.combat.barriers import absorb_damage, clear_barrier
from src.utils.durability import require_durable
from src.utils.gold_atomic import operation_id
from src.utils.ground_state import GROUND_TTL_SECONDS, GroundState, stack_identity
from src.utils.redis_config import RedisKeys
from src.utils.resource_transaction import Decision, Resource, Snapshot, transact
from src.utils.slot_plan import SlotPlan

if TYPE_CHECKING:
    from redis.asyncio import Redis

    from src.models.npc import NPC

PRIEST_RANGE = 2
MAX_DEATH_DROPS = 3
GHOST_BODY = 500
GHOST_HEAD = 500
MIN_PENALIZED_EXP = 100
EXP_PENALTY_DIVISOR = 20
GOLD_DROP_DIVISOR = 10


def hp_changes(
    stats: dict[str, str], position: dict[str, str], hp: int, event: str
) -> dict[str, str]:
    """Marca el daño letal y su posición en el mismo commit del HP.

    Returns:
        Campos canónicos y alias legacy, con evento asociado a la vida actual.
    """
    changes = {"min_hp": str(hp)}
    if "hp" in stats:
        changes["hp"] = str(hp)
    if hp <= 0 and int(stats.get("min_hp", stats.get("hp", 0))) > 0:
        changes.update(
            {
                "life_id": stats.get("life_id", "0"),
                "death_state": "pending",
                "poisoned_until": "0",
                "hidden_until": "0",
                "invisible_until": "0",
                "periodic_effects": "[]",
                **clear_barrier(),
                "death_event": event,
                "death_map": position.get("map", "1"),
                "death_x": position.get("x", "50"),
                "death_y": position.get("y", "50"),
            }
        )
    return changes


def revive_changes(stats: dict[str, str]) -> dict[str, str]:
    """Operación común para sacerdote y hechizo: misma generación, HP y flags.

    Returns:
        Restauración de media vida en el lugar y nueva generación.

    Raises:
        ValueError: Si está vivo o su muerte todavía no está liquidada.
    """
    if int(stats.get("min_hp", stats.get("hp", 0))) > 0 or stats.get("death_state") != "complete":
        message = "Sólo puedes resucitar una muerte ya liquidada."
        raise ValueError(message)
    hp = str(max(1, int(stats.get("max_hp", 100)) // 2))
    return {
        "min_hp": hp,
        **({"hp": hp} if "hp" in stats else {}),
        "life_id": str(int(stats.get("life_id", 0)) + 1),
        "death_state": "alive",
        "morphed_body": "0",
        "morphed_head": "0",
        "morphed_until": "0",
        "poisoned_until": "0",
        "immobilized_until": "0",
        "dumb_until": "0",
        "blinded_until": "0",
        "invisible_until": "0",
        "periodic_effects": "[]",
        **clear_barrier(),
    }


async def apply_player_damage(
    redis: Redis, user_id: int, damage: int, identity: str, *, require_poison: bool = False
) -> dict[str, Any]:
    """Daño físico/veneno relativo; dos golpes no pisan HP ni reviven una vida anterior.

    Returns:
        HP y generación afectados; un replay no aplica daño otra vez.
    """
    stats_key, position_key = (
        RedisKeys.player_user_stats(user_id),
        RedisKeys.player_position(user_id),
    )

    def decide(snapshot: Snapshot) -> Decision:
        stats = cast("dict[str, str]", snapshot[stats_key])
        position = cast("dict[str, str]", snapshot[position_key])
        hp = int(stats.get("min_hp", stats.get("hp", 0)))
        result = {
            "life_id": int(stats.get("life_id", 0)),
            "new_hp": hp,
            "player_died": False,
            "applied": False,
        }
        if (
            hp <= 0
            or damage < 1
            or (require_poison and float(stats.get("poisoned_until", 0)) <= time.time())
        ):
            return Decision(result, {})
        remaining, barrier = absorb_damage(
            stats, damage, "poison" if require_poison else "physical"
        )
        new_hp = max(0, hp - remaining)
        result.update({"new_hp": new_hp, "player_died": new_hp <= 0, "applied": True})
        return Decision(
            result, {stats_key: {**barrier, **hp_changes(stats, position, new_hp, identity)}}
        )

    return await transact(
        redis,
        (Resource(stats_key, "hash"), Resource(position_key, "hash")),
        identity,
        {"damage": user_id, "amount": damage, "poison": require_poison},
        decide,
    )


async def settle_death(
    redis: Redis, user_id: int, life_id: int, map_id: int, x: int, y: int
) -> dict[str, Any]:
    """Penalización, suelo, inventario, equipo y fantasma se confirman una vez por vida.

    Returns:
        Resultado estable. Los drops sin espacio permanecen en el inventario o saldo.
    """
    stats_key, inv_key, equip_key = (
        RedisKeys.player_user_stats(user_id),
        RedisKeys.player_inventory(user_id),
        RedisKeys.player_equipment(user_id),
    )
    ground_key = RedisKeys.ground_items(map_id)
    resources = (
        Resource(stats_key, "hash"),
        Resource(inv_key, "hash"),
        Resource(equip_key, "hash"),
        Resource(ground_key, "string", GROUND_TTL_SECONDS),
    )

    def decide(snapshot: Snapshot) -> Decision:
        stats = cast("dict[str, str]", snapshot[stats_key])
        if (
            int(stats.get("life_id", 0)) != life_id
            or int(stats.get("min_hp", stats.get("hp", 0))) > 0
            or stats.get("death_state") == "complete"
        ):
            return Decision({"applied": False}, {})
        inventory = SlotPlan(cast("dict[str, str]", snapshot[inv_key]), 30, 20)
        equipment = cast("dict[str, str]", snapshot[equip_key]).copy()
        ground = GroundState(map_id, cast("str | None", snapshot[ground_key]))
        experience = int(stats.get("experience", 0))
        gold = int(stats.get("gold", 0))
        pending = stats.get("death_state") == "pending"
        loss = (
            experience // EXP_PENALTY_DIVISOR if pending and experience >= MIN_PENALIZED_EXP else 0
        )
        dropped_gold = gold // GOLD_DROP_DIVISOR if pending else 0
        fraction = split_remainder(
            int(cast("dict[str, str]", snapshot.get(tax_key(user_id)) or {}).get("remainder", 0)),
            dropped_gold,
            gold + int(str(snapshot.get(RedisKeys.bank_gold(user_id)) or 0)),
        )
        event = stats.get("death_event", f"legacy:{user_id}:{life_id}")
        if pending and dropped_gold:
            try:
                ground.append(
                    x,
                    y,
                    {
                        "item_id": GOLD_ITEM_ID,
                        "quantity": dropped_gold,
                        "grh_index": 511,
                        "stack_id": stack_identity(event + ":gold"),
                        "devaluation_remainder": fraction.moved,
                    },
                )
            except ValueError:
                dropped_gold = 0
        slots = sorted(inventory.slots)
        selected = (
            random.Random(event).sample(slots, min(len(slots), MAX_DEATH_DROPS)) if pending else []
        )
        for slot in selected:
            stack = inventory.slots[slot]
            item = ITEMS_CATALOG.get(stack.item_id)
            if item is None:
                continue
            try:
                ground.append(
                    x,
                    y,
                    {
                        "item_id": stack.item_id,
                        "quantity": stack.quantity,
                        "grh_index": item.graphic_id,
                        "stack_id": stack_identity(event + f":slot:{slot}"),
                    },
                )
            except ValueError:
                continue
            inventory.take(slot, stack.item_id, stack.quantity)
            for field, value in equipment.items():
                if value == str(slot):
                    equipment[field] = "0"
        return Decision(
            {"applied": True, "life_id": life_id, "exp_loss": loss, "gold_drop": dropped_gold},
            {
                stats_key: {
                    "min_hp": "0",
                    **({"hp": "0"} if "hp" in stats else {}),
                    "death_state": "complete",
                    "life_id": str(life_id),
                    "experience": str(experience - loss),
                    "gold": str(gold - dropped_gold),
                    "morphed_body": str(GHOST_BODY),
                    "morphed_head": str(GHOST_HEAD),
                    "morphed_until": str(time.time() + 31536000),
                    "poisoned_until": "0",
                    "hidden_until": "0",
                    "invisible_until": "0",
                    "immobilized_until": "0",
                    "blinded_until": "0",
                    "dumb_until": "0",
                },
                inv_key: inventory.fields(),
                equip_key: equipment,
                ground_key: ground.encode(),
                **(
                    {tax_key(user_id): {"remainder": str(fraction.remaining)}}
                    if dropped_gold and fraction.moved
                    else {}
                ),
            },
        )

    await require_durable(redis)
    result = await transact(
        redis,
        resources,
        operation_id(),
        {"death": user_id, "life": life_id, "map": map_id, "x": x, "y": y},
        decide,
    )
    await require_durable(redis)
    return result


async def resurrect(
    redis: Redis, user_id: int, identity: str, *, priest: NPC | None = None
) -> dict[str, Any]:
    """Resurrección del sacerdote en el lugar; HP/flags/generación en el mismo EXEC.

    Returns:
        Confirmación única o rechazo sin efectos sobre un vivo.
    """
    key = RedisKeys.player_user_stats(user_id)
    resources = [Resource(key, "hash")]
    if priest:
        resources.extend(
            [
                Resource(RedisKeys.player_position(user_id), "hash"),
                Resource(RedisKeys.npc_instance(priest.instance_id), "hash"),
            ]
        )

    def decide(snapshot: Snapshot) -> Decision:
        stats = cast("dict[str, str]", snapshot[key])
        if priest:
            position = cast("dict[str, str]", snapshot[RedisKeys.player_position(user_id)])
            npc = cast("dict[str, str]", snapshot[RedisKeys.npc_instance(priest.instance_id)])
            allowed = config_manager.get("game.spells.resurrection_npc_ids", [81, 82, 119])
            if (
                not npc
                or int(npc.get("hp", 0)) <= 0
                or int(npc.get("npc_id", 0)) not in (allowed if isinstance(allowed, list) else [])
                or int(position.get("map", 0)) != int(npc.get("map_id", -1))
                or max(
                    abs(int(position.get("x", 0)) - int(npc.get("x", 0))),
                    abs(int(position.get("y", 0)) - int(npc.get("y", 0))),
                )
                > PRIEST_RANGE
            ):
                return Decision(
                    {
                        "applied": False,
                        "message": "Debes estar cerca de un sacerdote del mismo mapa.",
                    },
                    {},
                )
        try:
            changes = revive_changes(stats)
        except ValueError as error:
            return Decision({"applied": False, "message": str(error)}, {})
        return Decision({"applied": True, "life_id": int(changes["life_id"])}, {key: changes})

    await require_durable(redis)
    result = await transact(
        redis,
        tuple(resources),
        identity,
        {"revive": user_id, "priest": priest.instance_id if priest else None},
        decide,
    )
    await require_durable(redis)
    return result
