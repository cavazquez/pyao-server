"""Defensa de guardias: objetivos explícitos, radio desde el puesto y sin XP gratis."""

import operator
import time
from typing import TYPE_CHECKING, Any, cast

from src.utils.gold_atomic import operation_id
from src.utils.redis_config import RedisKeys
from src.utils.resource_transaction import Decision, Resource, Snapshot, transact

if TYPE_CHECKING:
    from src.models.npc import NPC
    from src.services.npc.npc_ai_service import NPCAIService

GUARD_RADIUS = 8


def guard_enemy(stats: dict[str, str], faction: str) -> bool:
    """Distingue criminales y facción enemiga de ciudadanos neutrales.

    Returns:
        Si el jugador es un objetivo permitido por la política del guardia.
    """
    criminal = str(stats.get("criminal", "0")).lower() in {"1", "true"}
    enemy = {"royal": "chaos", "chaos": "royal"}.get(faction)
    return criminal or bool(enemy and stats.get("faction_id") == enemy)


async def defend(ai: NPCAIService, guard: NPC) -> None:
    """Mantiene el puesto y sólo ataca objetivos vivos del mismo mapa."""
    if guard.hp <= 0 or guard.is_tamed or guard.paralyzed_until > time.time():
        return
    home_x, home_y = guard.home_x or guard.x, guard.home_y or guard.y

    def in_post(x: int, y: int) -> bool:
        return abs(x - home_x) + abs(y - home_y) <= GUARD_RADIUS

    candidates: list[tuple[int, int, int, int, NPC | None]] = []
    for user in ai.map_manager.get_players_in_map(guard.map_id):
        stats = await ai.player_repo.redis.hgetall(RedisKeys.player_user_stats(user))
        position = await ai.player_repo.get_position(user)
        if (
            position
            and int(stats.get("min_hp", 0)) > 0
            and position["map"] == guard.map_id
            and in_post(position["x"], position["y"])
            and guard_enemy(stats, guard.guard_faction)
        ):
            candidates.append(
                (
                    abs(guard.x - position["x"]) + abs(guard.y - position["y"]),
                    user,
                    position["x"],
                    position["y"],
                    None,
                )
            )
    candidates.extend(
        (abs(guard.x - target.x) + abs(guard.y - target.y), 0, target.x, target.y, target)
        for target in ai.map_manager.get_npcs_in_map(guard.map_id)
        if target.hp > 0
        and target.is_hostile
        and target.role != "guard"
        and not target.is_tamed
        and not target.summoned_by_user_id
        and in_post(target.x, target.y)
    )
    if not candidates:
        if (guard.x, guard.y) != (home_x, home_y):
            await ai.try_move_towards(guard, home_x, home_y)
        return
    distance, user, x, y, npc = min(candidates, key=operator.itemgetter(0))
    if distance != 1:
        await ai.try_move_towards(guard, x, y)
    elif user:
        # Comprobar otra vez la política inmediatamente antes de atacar.
        stats = await ai.player_repo.redis.hgetall(RedisKeys.player_user_stats(user))
        if guard_enemy(stats, guard.guard_faction):
            await ai.try_attack_player(guard, user)
    elif npc:
        await attack_creature(ai, guard, npc)


async def attack_creature(ai: NPCAIService, guard: NPC, target: NPC) -> None:
    """Confirma daño y cadencia juntos; un guardia no concede experiencia al observador."""
    now = time.time()
    guard_key, target_key = (RedisKeys.npc_instance(row.instance_id) for row in (guard, target))

    def decide(snapshot: Snapshot) -> Decision:
        own, enemy = (cast("dict[str, str]", snapshot[key]) for key in (guard_key, target_key))
        if not own or not enemy or int(own.get("hp", 0)) <= 0 or int(enemy.get("hp", 0)) <= 0:
            return Decision({"applied": False}, {})
        invalid_victim = (
            enemy.get("is_hostile", "").lower() != "true"
            or enemy.get("is_tamed", "").lower() == "true"
            or int(enemy.get("summoned_by_user_id", 0))
        )
        invalid_guard = own.get("role") != "guard" or float(own.get("paralyzed_until", 0)) > now
        outside_post = (
            abs(int(enemy["x"]) - int(own.get("home_x", own["x"])))
            + abs(int(enemy["y"]) - int(own.get("home_y", own["y"])))
            > GUARD_RADIUS
        )
        separated = (
            own.get("map_id") != enemy.get("map_id")
            or abs(int(own["x"]) - int(enemy["x"])) + abs(int(own["y"]) - int(enemy["y"])) != 1
        )
        cooling = now - float(own.get("last_attack_time", 0)) < float(own.get("attack_cooldown", 3))
        if invalid_victim or invalid_guard or outside_post or separated or cooling:
            return Decision({"applied": False}, {})
        hp = max(0, int(enemy["hp"]) - max(1, int(own.get("attack_damage", 10))))
        return Decision(
            {"applied": True, "hp": hp},
            {
                guard_key: {**own, "last_attack_time": str(now)},
                target_key: {**enemy, "hp": str(hp)},
            },
        )

    result: dict[str, Any] = await transact(
        ai.player_repo.redis.redis,
        (Resource(guard_key, "hash"), Resource(target_key, "hash")),
        operation_id(),
        {"guard": guard.instance_id, "target": target.instance_id},
        decide,
    )
    if not result["applied"]:
        return
    guard.last_attack_time, target.hp = now, int(result["hp"])
    if target.snd2:
        await ai.broadcast_service.broadcast_play_wave(
            target.map_id, target.snd2, target.x, target.y
        )
    if target.hp <= 0 and ai.npc_death_service:
        await ai.npc_death_service.handle_npc_death(
            target, 0, 0, None, death_reason="defensa de guardia"
        )
