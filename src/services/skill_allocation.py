"""Asignación de niveles con presupuesto y recibo idempotente en una sola transacción."""

from typing import TYPE_CHECKING, Any, cast

from src.config.config_manager import ConfigManager, config_manager
from src.models.skills import CATALOG, MAX_SKILL_LEVEL, skill_progress
from src.network.msg_skills import MAX_FREE_SKILL_POINTS, build_skill_catalog_response
from src.network.packet_builder import PacketBuilder
from src.utils.durability import require_durable
from src.utils.gold_atomic import operation_id
from src.utils.redis_config import RedisKeys
from src.utils.resource_transaction import Decision, Resource, Snapshot, transact

if TYPE_CHECKING:
    from redis.asyncio import Redis

    from src.messaging.message_sender import MessageSender
    from src.repositories.player_repository import PlayerRepository

STATE_ID = 254
MAX_OPERATION_ID_BYTES = 46


async def allocate_skill_points(
    redis: Redis, user_id: int, identity: str, deltas: tuple[tuple[int, int], ...]
) -> dict[str, Any]:
    """Confirma todos los deltas y el saldo juntos, sin modificar XP ni valores históricos.

    Returns:
        Resultado estable si se repite el ID con el mismo contenido.

    Raises:
        ValueError: Si los IDs no son los 22 canónicos en orden o la petición cambia de contenido.
    """
    if tuple(skill_id for skill_id, _ in deltas) != tuple(entry.skill_id for entry in CATALOG):
        message = "IDs de habilidades inválidos"
        raise ValueError(message)
    key = RedisKeys.player_skills(user_id)
    threshold = ConfigManager.as_int(config_manager.get("game.work.exp_per_level", 100))

    def decide(snapshot: Snapshot) -> Decision:
        values = cast("dict[str, str]", snapshot[key])
        progress = skill_progress(values, threshold)
        points = int(values.get("points", 0))
        spent = sum(delta for _, delta in deltas)
        if not 0 <= points <= MAX_FREE_SKILL_POINTS or spent < 1 or spent > points:
            return Decision({"applied": False, "message": "Puntos disponibles insuficientes."}, {})
        changes: dict[str, str] = {
            "points": str(points - spent),
            "assigned_points": str(min(10, int(values.get("assigned_points", 0)) + spent)),
        }
        for entry, (_, delta) in zip(progress, deltas, strict=True):
            definition = entry.definition
            available = definition.implemented and definition.key is not None
            if type(delta) is not int or delta < 0 or entry.level + delta > MAX_SKILL_LEVEL:
                return Decision({"applied": False, "message": "Delta inválido."}, {})
            if delta and not available:
                return Decision({"applied": False, "message": "Habilidad no disponible."}, {})
            if delta and definition.key is not None:
                changes[f"level:{definition.key}"] = str(entry.level + delta)
        return Decision({"applied": True, "message": "Asignación guardada."}, {key: changes})

    await require_durable(redis)
    result = await transact(
        redis, (Resource(key, "hash"),), identity, {"allocate": user_id, "deltas": deltas}, decide
    )
    await require_durable(redis)
    return result


async def send_allocation_state(
    sender: MessageSender,
    player: PlayerRepository,
    user_id: int,
    *,
    identity: str = "",
    status: int = 0,
    message: str = "",
) -> None:
    """Envía un snapshot coherente, un resultado correlacionado y el próximo ID del servidor."""
    values = await player.redis.hgetall(RedisKeys.player_skills(user_id))
    await sender.connection.send(
        build_allocation_state(values, identity=identity, status=status, message=message)
    )


def build_allocation_state(
    values: dict[str, str],
    *,
    identity: str = "",
    status: int = 0,
    message: str = "",
    next_identity: str | None = None,
) -> bytes:
    """Serializa el mismo snapshot que se entrega a Godot.

    Returns:
        Paquete 254 con IDs correlacionados y el catálogo de 22 habilidades.
    """
    threshold = ConfigManager.as_int(config_manager.get("game.work.exp_per_level", 100))
    catalog = build_skill_catalog_response(
        skill_progress(values, threshold), int(values.get("points", 0))
    )
    return (
        PacketBuilder()
        .add_byte(STATE_ID)
        .add_byte(1)
        .add_unicode_string(identity)
        .add_unicode_string(next_identity or operation_id())
        .add_byte(status)
        .add_unicode_string(message[:160])
        .to_bytes()
        + catalog[2:]
    )
