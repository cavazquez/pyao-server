"""Mantenimiento económico acotado, incluso con el mundo sin jugadores."""

import asyncio
import contextlib
import logging
from typing import TYPE_CHECKING

from redis.exceptions import RedisError

from src.economy.merchant_stock import restock_merchant
from src.economy.tax_service import settle_user_taxes

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from redis.asyncio import Redis

logger = logging.getLogger(__name__)


class EconomyMaintenance:
    """Recorre perfiles con SCAN sin detener el tick, y se drena antes de Redis."""

    def __init__(self, redis: Redis) -> None:
        """Conserva la conexión y la propiedad de la tarea de mantenimiento."""
        self.redis = redis
        self.task: asyncio.Task[None] | None = None

    def start(self) -> None:
        """Inicia una única tarea propiedad del servidor."""
        if self.task is None or self.task.done():
            self.task = asyncio.create_task(self._run(), name="economy-maintenance")

    async def _run(self) -> None:
        while True:
            try:
                await self._sweep("player:*:user_stats", settle_user_taxes)
                await self._sweep("merchant:*:catalog", restock_merchant)
            except RedisError, RuntimeError, ValueError:
                logger.exception("Mantenimiento económico pendiente; se reintentará")
            await asyncio.sleep(60)

    async def _sweep(self, pattern: str, action: Callable[[Redis, int], Awaitable[object]]) -> None:
        """Aísla registros inválidos para que no bloqueen los recursos siguientes."""
        async for key in self.redis.scan_iter(match=pattern, count=128):
            name = key.decode() if isinstance(key, bytes) else key
            try:
                await action(self.redis, int(name.split(":")[1]))
            except RedisError, RuntimeError, ValueError:
                logger.exception("Recurso económico pendiente: %s", name)
            await asyncio.sleep(0)

    async def close(self) -> None:
        """Cancela el barrido; los recibos resuelven un commit interrumpido."""
        if self.task:
            self.task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.task
            self.task = None
