"""Consumo de alimentos y bebidas: inventario y efectos en un único commit durable."""

from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, Any, cast

from src.models.item_types import ObjType
from src.utils.durability import require_durable
from src.utils.redis_config import RedisKeys
from src.utils.resource_transaction import Decision, Resource, Snapshot, transact
from src.utils.slot_plan import SlotPlan

if TYPE_CHECKING:
    from redis.asyncio import Redis

EMPTY_WATERSKIN = 534
MAX_RESTORE = 1000


@dataclass(frozen=True)
class NutritionRule:
    """Valores reales del catálogo, sin limitar la comida a una manzana concreta."""

    item_id: int
    hunger: int
    water: int
    hp: int
    stamina: int
    empty_item: int = 0

    @classmethod
    def from_item(cls, item_id: int, raw: dict[str, object]) -> NutritionRule:
        """Normaliza las dos grafías históricas de hambre sin perder otros efectos.

        Returns:
            Regla acotada para comida, bebida u odre lleno.

        Raises:
            ValueError: Si el tipo o los efectos no pertenecen a un consumible válido.
        """
        obj_type = raw.get("ObjType")
        amounts = tuple(
            int(str(raw.get(key, fallback)))
            for key, fallback in (
                ("MinHam", raw.get("MinHAM", 0)),
                ("MinAgu", 0),
                ("MinHP", 0),
                ("MinST", 0),
            )
        )
        if obj_type not in {ObjType.COMIDA, ObjType.BEBIDA, ObjType.BOTELLAS_LLENAS} or not all(
            0 <= amount <= MAX_RESTORE for amount in amounts
        ):
            message = "Alimento o bebida sin efectos válidos"
            raise ValueError(message)
        hunger, water, hp, stamina = amounts
        return cls(
            item_id,
            hunger,
            water,
            hp,
            stamina,
            EMPTY_WATERSKIN if obj_type == ObjType.BOTELLAS_LLENAS else 0,
        )


async def consume_nutrition(
    redis: Redis,
    user_id: int,
    slot: int,
    identity: str,
    rule: NutritionRule,
    capacity: int,
    max_stack: int,
) -> dict[str, Any]:
    """Una unidad, sus efectos y el envase vacío se acreditan juntos o no se aplican.

    Returns:
        Resultado identificado, sin consumir recursos de un slot cambiado o jugador muerto.
    """
    inventory, stats, hunger = (
        RedisKeys.player_inventory(user_id),
        RedisKeys.player_user_stats(user_id),
        RedisKeys.player_hunger_thirst(user_id),
    )
    resources = tuple(Resource(key, "hash") for key in (inventory, stats, hunger))

    def decide(snapshot: Snapshot) -> Decision:
        health = cast("dict[str, str]", snapshot[stats])
        needs = cast("dict[str, str]", snapshot[hunger])
        if int(health.get("min_hp", 0)) <= 0:
            return Decision(
                {"applied": False, "message": "No podés comer ni beber estando muerto."}, {}
            )
        plan = SlotPlan(cast("dict[str, str]", snapshot[inventory]), capacity, max_stack)
        try:
            plan.take(slot, rule.item_id, 1)
            if rule.empty_item:
                plan.give(rule.empty_item, 1)
        except ValueError as error:
            return Decision({"applied": False, "message": str(error)}, {})
        health_changes = {
            field: str(min(int(health.get(maximum, 100)), int(health.get(field, 0)) + restore))
            for field, maximum, restore in (
                ("min_hp", "max_hp", rule.hp),
                ("min_sta", "max_sta", rule.stamina),
            )
        }
        need_changes = {
            field: str(min(int(needs.get(maximum, 100)), int(needs.get(field, 0)) + restore))
            for field, maximum, restore in (
                ("min_hunger", "max_hunger", rule.hunger),
                ("min_water", "max_water", rule.water),
            )
        }
        for field, flag in (("min_hunger", "hunger_flag"), ("min_water", "thirst_flag")):
            need_changes[flag] = "1" if int(need_changes[field]) == 0 else "0"
        return Decision(
            {
                "applied": True,
                "item_id": rule.item_id,
                "effects": {**health_changes, **need_changes},
            },
            {inventory: plan.fields(), stats: health_changes, hunger: need_changes},
        )

    await require_durable(redis)
    result = await transact(
        redis,
        resources,
        identity,
        {"nutrition": user_id, "slot": slot, "rule": asdict(rule)},
        decide,
    )
    await require_durable(redis)
    return result
