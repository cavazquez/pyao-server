"""Plan de migración de habilidades legacy con sus campos originales intactos."""

from typing import TYPE_CHECKING, cast

from src.config.config_manager import ConfigManager, config_manager
from src.models.skills import skill_migration_fields
from src.services.player_progression import level_points_between
from src.utils.redis_config import RedisKeys

if TYPE_CHECKING:
    from redis import Redis


def skill_repairs(client: Redis) -> dict[str, dict[str, str]]:
    """Prepara campos de progreso sin escribir ni modificar los valores legacy.

    Returns:
        Hashes afectados y campos nuevos; el ejecutor confirma junto al journal.
    """
    threshold = ConfigManager.as_int(config_manager.get("game.work.exp_per_level", 100))
    result = {}
    for key in client.scan_iter(match="player:*:skills"):
        values = cast("dict[str, str]", client.hgetall(key))
        fields = skill_migration_fields(values, threshold)
        if fields:
            user_id = int((key.decode() if isinstance(key, bytes) else key).split(":")[1])
            stats = cast("dict[str, str]", client.hgetall(RedisKeys.player_user_stats(user_id)))
            level = max(1, int(stats.get("level", 1)))
            granted = max(1, int(values.get("points_granted_through", 1)))
            fields["points"] = str(
                int(values.get("points", fields.get("points", 10)))
                + level_points_between(granted, level)
            )
            fields["points_granted_through"] = str(max(granted, level))
            result[key.decode() if isinstance(key, bytes) else key] = fields
    return result
