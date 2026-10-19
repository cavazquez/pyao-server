"""Plan idempotente de reparación de maná legado, usado sólo por la migración v2."""

from typing import TYPE_CHECKING

from src.models.mana import MAX_MANA

if TYPE_CHECKING:
    from redis import Redis


def mana_repairs(client: Redis) -> dict[str, dict[str, str]]:
    """Detecta hashes afectados sin escribir ni modificar economía/progreso.

    Returns:
        Cambios mínimos y valores originales para auditoría por personaje.

    """
    repairs = {}
    for key in client.scan_iter(match="player:*:user_stats"):
        values = client.hmget(key, ["min_mana", "max_mana"])
        current, maximum = (int(value) if value is not None else 100 for value in values)
        normalized_max = min(MAX_MANA, max(0, maximum))
        normalized_current = min(normalized_max, max(0, current))
        if (current, maximum) == (normalized_current, normalized_max):
            continue
        name = key.decode() if isinstance(key, bytes) else key
        repairs[name] = {
            "min_mana": str(normalized_current),
            "max_mana": str(normalized_max),
            "migration:mana:current_before": str(current),
            "migration:mana:maximum_before": str(maximum),
        }
    return repairs
