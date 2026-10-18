"""Aprendizaje autoritativo: pergamino, requisitos y libro se confirman juntos."""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

from src.models.skills import skill_progress
from src.utils.durability import require_durable
from src.utils.redis_config import RedisKeys
from src.utils.resource_transaction import Decision, Resource, Snapshot, transact
from src.utils.slot_plan import SlotPlan

if TYPE_CHECKING:
    from redis.asyncio import Redis

MAX_BOOK_SLOTS = 35
MAX_INVENTORY_SLOTS = 30
MAX_INVENTORY_STACK = 20


@dataclass(frozen=True)
class ScrollRule:
    """Relación del catálogo y política explícita de aprendizaje."""

    item_id: int
    spell_id: int
    minimum_level: int
    minimum_magic: int
    allowed_classes: tuple[int, ...]


async def learn_scroll(
    redis: Redis, user_id: int, username: str, slot: int, identity: str, rule: ScrollRule
) -> dict[str, Any]:
    """Consume una unidad sólo si el personaje aprende el hechizo en el mismo EXEC.

    Returns:
        Resultado estable, slot de libro y mensaje sin cambios parciales.
    """
    inventory, book, stats, skills, account = (
        RedisKeys.player_inventory(user_id),
        RedisKeys.player_spellbook(user_id),
        RedisKeys.player_user_stats(user_id),
        RedisKeys.player_skills(user_id),
        RedisKeys.account_data(username),
    )
    resources = tuple(Resource(key, "hash") for key in (inventory, book, stats, skills, account))

    def decide(snapshot: Snapshot) -> Decision:
        values = {key: cast("dict[str, str]", snapshot[key]) for key in snapshot}
        saved, owner, known = values[stats], values[account], values[book]
        message = ""
        if int(owner.get("user_id", 0)) != user_id:
            message = "Personaje no disponible."
        elif int(saved.get("min_hp", saved.get("hp", 0))) <= 0:
            message = "No puedes aprender estando muerto."
        elif int(owner.get("char_job", 0)) not in rule.allowed_classes:
            message = "Tu clase no puede aprender este hechizo."
        elif int(saved.get("level", 1)) < rule.minimum_level:
            message = "Nivel insuficiente para aprender este hechizo."
        elif skill_progress(values[skills])[0].level < rule.minimum_magic:
            message = "Magia insuficiente para aprender este hechizo."
        elif str(rule.spell_id) in known.values():
            message = "Ya conoces ese hechizo."
        free = next(
            (
                index
                for index in range(1, MAX_BOOK_SLOTS + 1)
                if not known.get(str(index)) or known[str(index)] == "0"
            ),
            None,
        )
        if not message and free is None:
            message = "El libro de hechizos está lleno."
        plan = SlotPlan(values[inventory], MAX_INVENTORY_SLOTS, MAX_INVENTORY_STACK)
        if not message:
            try:
                plan.take(slot, rule.item_id, 1)
            except ValueError as error:
                message = str(error)
        if message:
            return Decision({"applied": False, "message": message}, {})
        return Decision(
            {
                "applied": True,
                "message": "Has aprendido el hechizo.",
                "book_slot": free,
                "spell_id": rule.spell_id,
            },
            {inventory: plan.fields(), book: {str(free): str(rule.spell_id)}},
        )

    await require_durable(redis)
    result = await transact(
        redis, resources, identity, {"learn": user_id, "slot": slot, "rule": rule.__dict__}, decide
    )
    await require_durable(redis)
    return result
