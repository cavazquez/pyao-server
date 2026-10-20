"""Experiencia individual y de party en el mismo commit que el botín del NPC."""

import json
import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

from src.models.party import LEVEL_EXPONENT, MAX_EXP_DISTANCE, MAX_PARTY_MEMBERS
from src.repositories.party_repository import PartyRepository
from src.services.player_progression import level_changes
from src.utils.redis_config import RedisKeys
from src.utils.resource_transaction import Resource, Snapshot

if TYPE_CHECKING:
    from redis.asyncio import Redis

MAX_EXPERIENCE = 2_147_483_647


class RewardContextChangedError(RuntimeError):
    """La composición cambió; reconstruir los recursos sin confirmar recompensas."""


@dataclass(frozen=True, slots=True)
class RewardContext:
    """Recursos de los destinatarios observados antes de WATCH."""

    killer: int
    party_id: int
    users: tuple[int, ...]
    resources: tuple[Resource, ...]


async def reward_context(redis: Redis, killer: int, saved: str | None) -> RewardContext:
    """Incluye también receptores offline de un plan pendiente ya congelado.

    Returns:
        Recursos completos para revalidar o aplicar la distribución una sola vez.

    Raises:
        ValueError: Si el plan o la composición de una party están corruptos.
    """
    if saved:
        plan = json.loads(saved)
        party_id = int(plan["party_id"])
        users = {int(user) for user in plan["xp_awards"]}
    else:
        party_id = int(await redis.get(f"user:{killer}:party") or 0) if killer > 0 else 0
        users = set()
    if party_id and not saved:
        members = await redis.hgetall(f"party:{party_id}:members")
        users.update(int(user) for user in members)
    users.update({killer} if killer > 0 else set())
    if len(users) > MAX_PARTY_MEMBERS + 1 or any(user < 1 for user in users):
        message = "Destinatarios de recompensa inválidos"
        raise ValueError(message)
    resources = [
        Resource(factory(user), "hash")
        for user in sorted(users)
        for factory in (
            RedisKeys.player_user_stats,
            RedisKeys.player_stats,
            RedisKeys.player_skills,
            RedisKeys.player_position,
        )
    ]
    resources.extend(Resource(f"user:{user}:party", "string") for user in sorted(users))
    if party_id:
        resources.extend(
            (
                Resource(f"party:{party_id}", "string"),
                Resource(f"party:{party_id}:members", "hash"),
                Resource(PartyRepository.ALL_PARTIES_KEY, "hash"),
            )
        )
    return RewardContext(killer, party_id, tuple(sorted(users)), tuple(resources))


def experience_plan(
    snapshot: Snapshot, context: RewardContext, total: int, map_id: int, x: int, y: int
) -> dict[str, Any]:
    """Aplica la fórmula clásica de party sobre el snapshot observado, sin I/O.

    Returns:
        Destinatarios/cantidades congelables aunque el suelo no tenga espacio.

    Raises:
        RewardContextChangedError: Si la pertenencia cambió antes de confirmar el plan.
    """
    killer, party_id = context.killer, context.party_id
    plan: dict[str, Any] = {"party_id": party_id, "xp_awards": {}, "total_exp": total}
    if killer < 1:
        return plan
    if int(str(snapshot[f"user:{killer}:party"] or 0)) != party_id:
        raise RewardContextChangedError
    if not party_id:
        plan["xp_awards"] = {str(killer): total}
        return plan
    raw = snapshot[f"party:{party_id}"]
    if not isinstance(raw, str):
        raise RewardContextChangedError
    party = json.loads(raw)
    members = cast("dict[str, str]", snapshot[f"party:{party_id}:members"])
    if set(map(int, members)) | {killer} != set(context.users):
        raise RewardContextChangedError
    denominator = float(party["sum_elevated_levels"])
    if denominator <= 0:
        return plan
    plan["party_created_at"] = party["created_at"]
    for user_string, row in members.items():
        user, member = int(user_string), json.loads(row)
        stats = cast("dict[str, str]", snapshot[RedisKeys.player_user_stats(user)])
        position = cast("dict[str, str]", snapshot[RedisKeys.player_position(user)])
        if (
            not member["is_online"]
            or not position
            or int(stats.get("min_hp", 0)) <= 0
            or int(position.get("map", 0)) != map_id
            or int(str(snapshot[f"user:{user}:party"] or 0)) != party_id
        ):
            continue
        distance = math.hypot(int(position["x"]) - x, int(position["y"]) - y)
        if int(distance) <= MAX_EXP_DISTANCE:
            level = max(1, int(stats.get("level", 1)))
            plan["xp_awards"][user_string] = math.floor(total * level**LEVEL_EXPONENT / denominator)
    return plan


def award_changes(
    snapshot: Snapshot, context: RewardContext, plan: dict[str, Any]
) -> tuple[dict[str, str | dict[str, str] | set[str]], dict[str, Any]]:
    """Actualiza experiencia, nivel, puntos y contabilidad de party una sola vez.

    Returns:
        Escrituras parciales y niveles confirmados para notificar después del commit.

    Raises:
        RewardContextChangedError: Si falta un destinatario de un plan congelado.
    """
    if not set(map(int, plan["xp_awards"])).issubset(context.users):
        raise RewardContextChangedError
    writes: dict[str, str | dict[str, str] | set[str]] = {}
    levels: dict[str, Any] = {}
    for user_string, amount in plan["xp_awards"].items():
        user = int(user_string)
        stats_key, skills_key = (
            RedisKeys.player_user_stats(user),
            RedisKeys.player_skills(user),
        )
        stats = cast("dict[str, str]", snapshot[stats_key])
        if not stats:
            continue
        experience = min(MAX_EXPERIENCE, int(stats.get("experience", 0)) + int(amount))
        changes, skills, result = level_changes(
            {**stats, "experience": str(experience)},
            cast("dict[str, str]", snapshot[RedisKeys.player_stats(user)]),
            cast("dict[str, str]", snapshot[skills_key]),
        )
        writes[stats_key] = {**changes, "experience": str(experience)}
        writes[skills_key] = skills
        levels[user_string] = {**result, "experience": experience, "awarded": amount}
    party_id = int(plan["party_id"])
    raw = snapshot.get(f"party:{party_id}") if party_id else None
    if isinstance(raw, str):
        party = json.loads(raw)
        if party["created_at"] == plan.get("party_created_at"):
            party["total_exp_earned"] += plan["total_exp"]
            members = cast("dict[str, str]", snapshot[f"party:{party_id}:members"])
            member_changes: dict[str, str] = {}
            for user_string, result in levels.items():
                if user_string not in members:
                    continue
                member = json.loads(members[user_string])
                member["accumulated_exp"] += result["awarded"]
                party["sum_elevated_levels"] += (
                    result["level"] ** LEVEL_EXPONENT - member["level"] ** LEVEL_EXPONENT
                )
                member["level"] = result["level"]
                member_changes[user_string] = json.dumps(member)
            writes[f"party:{party_id}:members"] = member_changes
            writes[f"party:{party_id}"] = json.dumps(party)
            writes[PartyRepository.ALL_PARTIES_KEY] = {str(party_id): json.dumps(party)}
    return writes, levels
