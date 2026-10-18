"""Plan de migración de habilidades legacy con sus campos originales intactos."""

from typing import TYPE_CHECKING, cast

from src.config.config_manager import ConfigManager, config_manager
from src.models.skills import skill_migration_fields

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
            result[key.decode() if isinstance(key, bytes) else key] = fields
    return result
