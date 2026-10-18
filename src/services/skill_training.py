"""Entrenamiento natural y recompensa general incluidos en la operación de juego."""

import json
from typing import TYPE_CHECKING, Any, cast

from src.models.skill_data_loader import SKILL_RULES_KEY
from src.models.skills import (
    MAX_SKILL_LEVEL,
    SKILLS_BY_KEY,
    skill_migration_fields,
    skill_threshold,
)
from src.services.player_progression import level_changes
from src.utils.gold_atomic import operation_id
from src.utils.redis_config import RedisKeys
from src.utils.resource_transaction import Decision, Resource, Snapshot, transact

if TYPE_CHECKING:
    from src.repositories.player_repository import PlayerRepository

type TrainingEvent = tuple[str, bool]


async def read_rules(player: PlayerRepository) -> dict[str, Any]:
    """Lee reglas de juego ya validadas y cargadas, sin abrir TOML durante una partida.

    Returns:
        Reglas del dataset propio o vacío en herramientas legacy sin inicialización.
    """
    raw = await player.redis.get(SKILL_RULES_KEY)
    return cast("dict[str, Any]", json.loads(raw)) if raw else {}


def training_resources(user_id: int) -> tuple[Resource, ...]:
    """Declara todos los recursos del progreso y recompensa.

    Returns:
        Hashes observados y catálogo de reglas inmutable durante el commit.
    """
    return (
        Resource(RedisKeys.player_skills(user_id), "hash"),
        Resource(RedisKeys.player_user_stats(user_id), "hash"),
        Resource(RedisKeys.player_stats(user_id), "hash"),
        Resource(RedisKeys.player_hunger_thirst(user_id), "hash"),
        Resource(SKILL_RULES_KEY, "string"),
    )


def trained_decision(  # noqa: PLR0914 - combina overlays del mismo commit, sin I/O
    decision: Decision, snapshot: Snapshot, user_id: int, events: tuple[TrainingEvent, ...]
) -> Decision:
    """Añade progreso a una decisión válida antes del EXEC, nunca después del coste.

    Returns:
        Cambios combinados de acción, nivel, XP y presupuesto de habilidades.
    """
    raw_rules = snapshot.get(SKILL_RULES_KEY)
    if not events or not isinstance(raw_rules, str) or not raw_rules:
        return decision
    rules = cast("dict[str, Any]", json.loads(raw_rules))
    skills_key, stats_key, attrs_key, hunger_key = (
        RedisKeys.player_skills(user_id),
        RedisKeys.player_user_stats(user_id),
        RedisKeys.player_stats(user_id),
        RedisKeys.player_hunger_thirst(user_id),
    )
    values = {key: dict(value) for key, value in snapshot.items() if isinstance(value, dict)}
    for key, changes in decision.writes.items():
        if isinstance(changes, dict):
            values.setdefault(key, {}).update(changes)
    skills, stats, hunger = values[skills_key], values[stats_key], values[hunger_key]
    if not stats or int(stats.get("min_hp", 0)) <= 0:
        return decision
    migration = skill_migration_fields(skills)
    skills.update(migration)
    if (
        int(skills.get("assigned_points", 0)) < int(rules["initial_assignment"])
        or int(hunger.get("hunger_flag", 0))
        or int(hunger.get("thirst_flag", 0))
        or int(hunger.get("min_hunger", 100)) <= 0
        or int(hunger.get("min_water", 100)) <= 0
    ):
        return decision
    level = max(1, int(stats.get("level", 1)))
    cap = int(rules["natural_caps"][min(level, len(rules["natural_caps"])) - 1])
    base = int(rules["xp_base"])
    skill_changes: dict[str, str] = {
        **migration,
        "progress_version": "2",
        "natural_xp_base": str(base),
    }
    improvements = []
    for key, success in events:
        definition = SKILLS_BY_KEY.get(key)
        current = int(skills.get(f"level:{key}", 0))
        if (
            definition is None
            or key in rules["manual_only"]
            or current >= min(MAX_SKILL_LEVEL, cap)
        ):
            continue
        gain = int(rules["success_xp"] if success else rules["failure_xp"])
        partial = int(skills.get(f"partial:{key}", 0)) + gain
        skill_changes[f"xp:{key}"] = str(int(skills.get(f"xp:{key}", 0)) + gain)
        required = skill_threshold(current, base)
        if partial >= required:
            partial -= required
            current += 1
            improvements.append(key)
            stats["experience"] = str(
                min(2147483647, int(stats.get("experience", 0)) + int(rules["character_xp"]))
            )
        skill_changes[f"partial:{key}"] = str(partial)
        skill_changes[f"level:{key}"] = str(current)
        skills.update(skill_changes)
    writes = dict(decision.writes)
    writes[skills_key] = {**cast("dict[str, str]", writes.get(skills_key, {})), **skill_changes}
    if improvements:
        stats_changes, point_changes, _result = level_changes(stats, values[attrs_key], skills)
        writes[stats_key] = {
            **cast("dict[str, str]", writes.get(stats_key, {})),
            "experience": stats["experience"],
            **stats_changes,
        }
        writes[skills_key].update(point_changes)  # type: ignore[union-attr]
    return Decision({**decision.result, "skills_improved": improvements}, writes)


async def train_skill(
    player: PlayerRepository,
    user_id: int,
    skill: str,
    *,
    successful: bool,
    identity: str | None = None,
) -> dict[str, Any]:
    """Entrena una acción elegible sin otro recurso de negocio que mutar.

    Returns:
        Resultado estable, incluidos los niveles de habilidad ganados.
    """
    return await transact(
        player.redis.redis,
        training_resources(user_id),
        identity or operation_id(),
        {"train": user_id, "skill": skill, "success": successful},
        lambda snapshot: trained_decision(
            Decision({"applied": True}, {}), snapshot, user_id, ((skill, successful),)
        ),
    )
