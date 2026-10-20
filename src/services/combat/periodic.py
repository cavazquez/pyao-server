"""Pulsos persistidos en el GameTick existente, sin tareas o timers propios."""

import json
import time
from typing import TYPE_CHECKING, Any, cast

from src.services.combat.barriers import absorb_damage, clear_barrier
from src.services.combat.pvp_policy import PvpPolicy
from src.services.player.lifecycle import hp_changes
from src.utils.gold_atomic import operation_id
from src.utils.redis_config import RedisKeys
from src.utils.resource_transaction import Decision, Resource, Snapshot, transact

if TYPE_CHECKING:
    from redis.asyncio import Redis


def periodic_changes(
    stats: dict[str, str], rule: dict[str, Any], now: float, identity: str, source: int
) -> dict[str, str]:
    """Reemplaza sólo el modo indicado y conserva el otro pulso.

    Returns:
        Estado de duración absoluta acotado a dos efectos.
    """
    rows = [
        row
        for row in json.loads(stats.get("periodic_effects", "[]"))
        if row["mode"] != rule["mode"] and float(row["until"]) > now
    ]
    rows.append(
        {
            **rule,
            "until": now + rule["duration_seconds"],
            "next": now + rule["interval_seconds"],
            "identity": identity,
            "source": source,
        }
    )
    return {"periodic_effects": json.dumps(rows, separators=(",", ":"))}


async def tick_periodic(redis: Redis, user: int) -> dict[str, Any]:
    """Ejecuta como máximo un pulso por efecto y reprograma desde el reloj actual.

    Returns:
        HP confirmado; los pulsos vencidos/offline no se acumulan al reconectar.
    """
    key, pos_key = RedisKeys.player_user_stats(user), RedisKeys.player_position(user)
    now = time.time()
    preview = await redis.hgetall(key)
    if preview.get("periodic_effects", "[]") == "[]" and preview.get("barrier_until", "0") == "0":
        return {"applied": False, "new_hp": int(preview.get("min_hp", 0))}

    def decide(snapshot: Snapshot) -> Decision:
        stats, pos = (cast("dict[str, str]", snapshot[name]) for name in (key, pos_key))
        rows = json.loads(stats.get("periodic_effects", "[]"))
        hp = int(stats.get("min_hp", 0))
        changes: dict[str, str] = {}
        active = []
        current = dict(stats)
        for row in rows:
            # El último pulso puede coincidir exactamente con el vencimiento.
            if hp <= 0 or now > float(row["until"]) + 1 or float(row["next"]) > float(row["until"]):
                continue
            if now >= float(row["next"]):
                if row["mode"] == "heal":
                    hp = min(int(stats.get("max_hp", 100)), hp + int(row["amount"]))
                elif int(pos.get("map", 0)) not in PvpPolicy.configured().safe_maps:
                    damage, barrier = absorb_damage(current, int(row["amount"]), "periodic", now)
                    changes.update(barrier)
                    current.update(barrier)
                    hp = max(0, hp - damage)
                row["next"] = now + int(row["interval_seconds"])
            active.append(row)
        if hp <= 0:
            active.clear()
        if float(stats.get("barrier_until", 0)) <= now and stats.get("barrier_until", "0") != "0":
            changes.update(clear_barrier())
        serialized = json.dumps(active, separators=(",", ":"))
        if serialized != stats.get("periodic_effects", "[]"):
            changes["periodic_effects"] = serialized
        if hp != int(stats.get("min_hp", 0)):
            changes.update(hp_changes(stats, pos, hp, f"periodic:{user}:{now}"))
        return Decision({"applied": bool(changes), "new_hp": hp}, {key: changes} if changes else {})

    # WATCH de next/HP evita que dos ticks coincidentes produzcan un pulso doble.
    return await transact(
        redis,
        (Resource(key, "hash"), Resource(pos_key, "hash")),
        operation_id(),
        {"periodic_tick": user, "time": now},
        decide,
    )
