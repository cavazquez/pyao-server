"""Cancelación excepcional por el operador autenticado mediante el secreto Redis."""

from typing import TYPE_CHECKING, Any

from redis.asyncio import Redis

from src.services.lottery.repository import LotteryRepository

if TYPE_CHECKING:
    from src.config.game_config import RedisConfig


async def cancel_round(config: RedisConfig, identity: str, reason: str) -> dict[str, Any]:
    """Registra el motivo; el worker del servidor reanuda devoluciones completas.

    Returns:
        Resultado durable. No requiere ni inicia el listener del juego.
    """
    async with Redis(
        host=config.host,
        port=config.port,
        db=config.db,
        password=config.read_password(),
        decode_responses=True,
        socket_connect_timeout=5,
        socket_timeout=10,
    ) as redis:
        return await LotteryRepository(redis).cancel(identity, reason)
