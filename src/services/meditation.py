"""Recuperación y entrenamiento de meditación con reloj persistente en Redis."""

import random
import time
from typing import TYPE_CHECKING, Any, cast

from src.models.skills import skill_progress
from src.services.skill_training import trained_decision, training_resources
from src.utils.gold_atomic import operation_id
from src.utils.redis_config import RedisKeys
from src.utils.resource_transaction import Decision, Snapshot, transact

if TYPE_CHECKING:
    from src.repositories.player_repository import PlayerRepository

MEDITATION_LUCK = (35, 30, 28, 24, 22, 20, 18, 15, 10, 7, 5)
MANA_RECOVERY_FRACTION = 0.05
SKILL_BAND = 10


async def meditate_tick(
    player: PlayerRepository, user_id: int, interval: float, *, now: float | None = None
) -> dict[str, Any]:
    """Confirma un solo intento vencido, sin entrenar con maná completo.

    Returns:
        Estado, maná confirmado y si debe finalizar el efecto visual.
    """
    timestamp = time.time() if now is None else now
    sample = random.random()
    key = RedisKeys.player_user_stats(user_id)

    def decide(snapshot: Snapshot) -> Decision:
        stats = cast("dict[str, str]", snapshot[key])
        if stats.get("meditating") != "1":
            return Decision({"applied": False}, {})
        mana, maximum = int(stats.get("min_mana", 0)), int(stats.get("max_mana", 0))
        if mana >= maximum or int(stats.get("min_hp", 0)) <= 0:
            return Decision({"applied": True, "stopped": True}, {key: {"meditating": "0"}})
        due = float(stats.get("meditation_due", 0))
        if due > timestamp:
            return Decision({"applied": False}, {})
        changes = {"meditation_due": str(timestamp + interval)}
        if due == 0:
            return Decision({"applied": False}, {key: changes})
        skills = cast("dict[str, str]", snapshot[RedisKeys.player_skills(user_id)])
        level = next(p.level for p in skill_progress(skills) if p.definition.key == "meditar")
        band = (
            max(0, (level - 1) // SKILL_BAND)
            if level < SKILL_BAND * len(MEDITATION_LUCK) - SKILL_BAND
            else len(MEDITATION_LUCK) - 1
        )
        success = sample < 1 / MEDITATION_LUCK[band]
        recovered = (
            min(maximum - mana, max(1, int(maximum * MANA_RECOVERY_FRACTION))) if success else 0
        )
        changes["min_mana"] = str(mana + recovered)
        stopped = mana + recovered >= maximum
        if stopped:
            changes["meditating"] = "0"
        return trained_decision(
            Decision(
                {
                    "applied": True,
                    "stopped": stopped,
                    "recovered": recovered,
                    "mana": mana + recovered,
                },
                {key: changes},
            ),
            snapshot,
            user_id,
            (("meditar", success),),
        )

    return await transact(
        player.redis.redis,
        training_resources(user_id),
        operation_id(),
        {"meditation": user_id, "at": timestamp},
        decide,
    )
