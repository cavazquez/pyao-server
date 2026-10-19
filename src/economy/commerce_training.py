"""Entrenamiento comercial por volumen confirmado y ventanas persistidas."""

import json
import time
from typing import cast

from src.services.skill_training import trained_decision
from src.utils.redis_config import RedisKeys
from src.utils.resource_transaction import Decision, Snapshot

GOLD_PER_TRAINING_EVENT = 100
MAX_EVENTS_PER_MINUTE = 4
MAX_ITEMS_PER_WINDOW = 64
WINDOW_SECONDS = 60


def train_commerce(
    decision: Decision,
    snapshot: Snapshot,
    user_id: int,
    item_id: int,
    action: str,
    *,
    now: float | None = None,
) -> Decision:
    """Cuenta volumen económico sin multiplicar XP por dividirlo en paquetes.

    Returns:
        Decisión original con presupuesto y entrenamiento en el mismo commit.
    """
    key = RedisKeys.player_skills(user_id)
    skills = cast("dict[str, str]", snapshot[key])
    window = int((time.time() if now is None else now) // WINDOW_SECONDS)
    current = skills.get("commerce:window") == str(window)
    directions = json.loads(skills.get("commerce:directions", "{}")) if current else {}
    remaining = int(skills.get("commerce:remainder", 0)) if current else 0
    used = int(skills.get("commerce:events", 0)) if current else 0
    item = str(item_id)
    previous = directions.get(item, action)
    if item in directions or len(directions) < MAX_ITEMS_PER_WINDOW:
        directions[item] = action if previous == action else "mixed"
    eligible = directions.get(item) == action
    volume = max(0, int(decision.result.get("total", 0))) if eligible else 0
    events, remaining = divmod(remaining + volume, GOLD_PER_TRAINING_EVENT)
    events = min(events, max(0, MAX_EVENTS_PER_MINUTE - used))
    if used + events >= MAX_EVENTS_PER_MINUTE:
        remaining = 0  # No se guarda volumen para entrenar en una ventana futura.
    trained = trained_decision(decision, snapshot, user_id, (("comerciar", True),) * events)
    writes = dict(trained.writes)
    writes[key] = {
        **cast("dict[str, str]", writes.get(key, {})),
        "commerce:window": str(window),
        "commerce:remainder": str(remaining),
        "commerce:events": str(used + events),
        "commerce:directions": json.dumps(directions, sort_keys=True, separators=(",", ":")),
    }
    return Decision(trained.result, writes)
