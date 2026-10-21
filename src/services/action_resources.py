"""Recursos de una acción del jugador, sin dependencias de combate o servicios UI."""

from src.services.skill_training import training_resources
from src.utils.redis_config import RedisKeys
from src.utils.resource_transaction import Resource


def player_action_resources(user: int) -> tuple[Resource, ...]:
    """Incluye equipo e inventario para evitar actuar con objetos que ya cambiaron.

    Returns:
        Recursos del actor para una operación completa.
    """
    return (
        *training_resources(user),
        Resource(RedisKeys.player_position(user), "hash"),
        Resource(RedisKeys.player_inventory(user), "hash"),
        Resource(RedisKeys.player_equipment(user), "hash"),
    )
