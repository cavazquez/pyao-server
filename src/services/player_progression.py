"""Crecimiento y skillpoints confirmados juntos desde la experiencia persistida."""

from typing import TYPE_CHECKING, Any, cast

from src.config.config_manager import ConfigManager, config_manager
from src.models.mana import MAX_MANA, calculate_mana
from src.models.skills import skill_progress
from src.utils.gold_atomic import operation_id
from src.utils.level_calculator import calculate_level_from_experience, calculate_remaining_elu
from src.utils.redis_config import RedisKeys
from src.utils.resource_transaction import Decision, Resource, Snapshot, transact

if TYPE_CHECKING:
    from src.messaging.message_sender import MessageSender
    from src.repositories.player_repository import PlayerRepository


FIRST_LEVEL_UP = 2


def level_points_between(previous: int, current: int) -> int:
    """Calcula puntos por niveles ganados: 1→2 concede diez, luego cinco.

    Returns:
        Presupuesto nuevo; nunca negativo.
    """
    return sum(
        10 if level == FIRST_LEVEL_UP else 5
        for level in range(max(FIRST_LEVEL_UP, previous + 1), current + 1)
    )


def level_changes(
    stats: dict[str, str], attributes: dict[str, str], skills: dict[str, str]
) -> tuple[dict[str, str], dict[str, str], dict[str, Any]]:
    """Deriva máximos y presupuesto del mismo snapshot, sin alterar oro ni experiencia.

    Returns:
        Cambios de stats, habilidades y resultado serializable.
    """
    old_level = max(1, int(stats.get("level", 1)))
    experience = max(0, int(stats.get("experience", 0)))
    new_level = max(old_level, calculate_level_from_experience(experience, config_manager))
    granted = max(1, int(skills.get("points_granted_through", old_level)))
    points = level_points_between(granted, new_level)
    skill_changes = {
        "points_granted_through": str(max(granted, new_level)),
        "points": str(int(skills.get("points", 0)) + points),
    }
    changes = {
        "level": str(new_level),
        "elu": str(calculate_remaining_elu(experience, new_level, config_manager)),
    }
    if new_level > old_level and attributes:
        hp_rate = ConfigManager.as_int(config_manager.get("game.character.hp_per_con", 10))
        mana_rate = ConfigManager.as_int(config_manager.get("game.character.mana_per_int", 10))
        maxima = {
            "hp": min(
                MAX_MANA, max(100, int(attributes.get("constitution", 10)) * hp_rate * new_level)
            ),
            "mana": max(
                100, calculate_mana(int(attributes.get("intelligence", 10)), mana_rate, new_level)
            ),
            "sta": min(MAX_MANA, 100 + new_level * 10),
        }
        for field, maximum in maxima.items():
            old_maximum = max(1, int(stats.get(f"max_{field}", maximum)))
            current = min(maximum, int(stats.get(f"min_{field}", 0)) * maximum // old_maximum)
            changes[f"max_{field}"] = str(maximum)
            changes[f"min_{field}"] = str(current)
        if "hp" in stats:
            changes["hp"] = changes["min_hp"]
    return (
        changes,
        skill_changes,
        {"previous_level": old_level, "level": new_level, "points_gained": points},
    )


async def advance_player_level(
    player: PlayerRepository, user_id: int, sender: MessageSender
) -> dict[str, Any]:
    """Avanza desde Redis y publica el resultado sin repetir concesiones concurrentes.

    Returns:
        Niveles y puntos concedidos por esta operación.
    """
    stats_key, attrs_key, skills_key = (
        RedisKeys.player_user_stats(user_id),
        RedisKeys.player_stats(user_id),
        RedisKeys.player_skills(user_id),
    )

    def decide(snapshot: Snapshot) -> Decision:
        stats = cast("dict[str, str]", snapshot[stats_key])
        if not stats:
            return Decision({"previous_level": 1, "level": 1, "points_gained": 0}, {})
        changes, skills, result = level_changes(
            stats,
            cast("dict[str, str]", snapshot[attrs_key]),
            cast("dict[str, str]", snapshot[skills_key]),
        )
        return Decision(result, {stats_key: changes, skills_key: skills})

    result = await transact(
        player.redis.redis,
        (Resource(stats_key, "hash"), Resource(attrs_key, "hash"), Resource(skills_key, "hash")),
        operation_id(),
        {"advance_level": user_id},
        decide,
    )
    await publish_progress(player, user_id, sender)
    if result["level"] > result["previous_level"]:
        await sender.play_sound_level_up()
        await sender.send_console_msg(f"¡Felicidades! Has subido al nivel {result['level']}!")
    return result


async def publish_progress(player: PlayerRepository, user_id: int, sender: MessageSender) -> None:
    """Actualiza stats y catálogo sólo cuando la conexión negoció esa capacidad."""
    from src.network.capabilities import Capability  # ruff: ignore[import-outside-top-level]
    from src.network.msg_skills import build_skill_catalog_response  # ruff: ignore[import-outside-top-level]

    await sender.send_update_user_stats_from_repo(user_id, player)
    if sender.connection.capabilities.enabled & Capability.SKILLS_CATALOG:
        values = await player.redis.hgetall(RedisKeys.player_skills(user_id))
        progress = skill_progress(values)
        points = int(values.get("points", 0))
        await sender.connection.send(build_skill_catalog_response(progress, points))
