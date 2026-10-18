"""Reserva Redis con propietario y TTL para una única sesión por cuenta."""

import asyncio
from secrets import token_urlsafe
from typing import TYPE_CHECKING

from redis.exceptions import WatchError

if TYPE_CHECKING:
    from redis.asyncio import Redis


class SessionLease:
    """Lease renovable; liberar o renovar nunca afecta al token de otra conexión."""

    def __init__(self, redis: Redis, user_id: int, ttl: int = 90) -> None:
        """Crea un token privado para reservar una cuenta autenticada."""
        self.redis = redis
        self.key = f"session:{user_id}:owner"
        self.token = token_urlsafe(32)
        self.ttl = ttl

    async def acquire(self) -> bool:
        """Reserva atómicamente antes de publicar el jugador.

        Returns:
            True si no existía otra reserva activa.

        Raises:
            CancelledError: Tras resolver y retirar una reserva cuyo SET seguía en vuelo.
        """
        pending = asyncio.ensure_future(self.redis.set(self.key, self.token, nx=True, ex=self.ttl))
        try:
            return bool(await asyncio.shield(pending))
        except asyncio.CancelledError:
            try:
                await pending
            finally:
                await self.release()
            raise

    async def _mutate_owned(self, *, release: bool) -> bool:
        for _ in range(3):
            async with self.redis.pipeline(transaction=True) as pipe:
                try:
                    await pipe.watch(self.key)
                    if await pipe.get(self.key) != self.token:
                        return False
                    pipe.multi()  # type: ignore[no-untyped-call]  # redis-py no anota multi.
                    if release:
                        pipe.delete(self.key)
                    else:
                        pipe.expire(self.key, self.ttl)
                    result = await pipe.execute()
                    return bool(result[0])
                except WatchError:
                    continue
        return False

    async def renew(self) -> bool:
        """Renueva únicamente si la reserva sigue perteneciendo a esta conexión.

        Returns:
            True si se confirmó la renovación.
        """
        return await self._mutate_owned(release=False)

    async def release(self) -> bool:
        """Libera sólo el token propio, incluso después de una expiración/reconexión.

        Returns:
            True si se retiró la reserva propia.
        """
        return await self._mutate_owned(release=True)
