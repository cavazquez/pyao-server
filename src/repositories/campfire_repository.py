"""Fogatas efímeras autoritativas en Redis, con descubrimiento acotado por mapa."""

import time
from typing import TYPE_CHECKING, cast

from redis.exceptions import WatchError

from src.constants.map import MAP_SIZE

REBUILD_BATCH = 256

if TYPE_CHECKING:
    from src.utils.redis_client import RedisClient


def campfire_index(map_id: int) -> str:
    """Devuelve el conjunto derivado de claves de fogata de un mapa.

    Returns:
        Clave Redis separada de los hashes de fogata.
    """
    return f"world:campfires:{map_id}"


def _position(key: str, data: dict[str, str], map_id: int, now: float) -> tuple[int, int] | None:
    try:
        x, y = int(data["x"]), int(data["y"])
        if (
            1 <= x <= MAP_SIZE
            and 1 <= y <= MAP_SIZE
            and key == f"world:campfire:{map_id}:{x}:{y}"
            and float(data.get("until", 0)) > now
        ):
            return x, y
    except ValueError, KeyError:
        return None
    return None


class CampfireRepository:
    """No recorre claves globales durante una consulta de juego."""

    def __init__(self, redis: RedisClient) -> None:
        """Conserva el cliente del mundo activo."""
        self.redis = redis

    async def positions(self, map_id: int, now: float) -> set[tuple[int, int]]:
        """Lee un conjunto y sus hashes en un lote; poda referencias obsoletas.

        Returns:
            Posiciones vigentes y validadas del mapa solicitado.
        """
        members: list[str] = sorted(await self.redis.smembers(campfire_index(map_id)))
        # Un índice corrupto nunca autoriza leer ni borrar claves ajenas.
        keys = [key for key in members if key.startswith(f"world:campfire:{map_id}:")]
        async with self.redis.redis.pipeline(transaction=False) as pipe:
            for key in keys:
                pipe.hgetall(key)
            rows = cast("list[dict[str, str]]", await pipe.execute())
        positions = set()
        stale = set(members) - set(keys)
        for key, row in zip(keys, rows, strict=True):
            position = _position(key, row, map_id, now)
            if position is None:
                stale.add(key)
            else:
                positions.add(position)
        if stale:
            await self._prune(map_id, stale, now)
        return positions

    async def _prune(self, map_id: int, stale: set[str], now: float) -> None:
        valid_prefix = f"world:campfire:{map_id}:"
        keys = sorted(key for key in stale if key.startswith(valid_prefix))
        for _ in range(3):
            async with self.redis.redis.pipeline() as pipe:
                try:
                    if keys:
                        await pipe.watch(*keys)
                    remove = stale - set(keys)
                    for key in keys:
                        row = cast("dict[str, str]", await pipe.hgetall(key))
                        if _position(key, row, map_id, now) is None:
                            remove.add(key)
                    pipe.multi()  # type: ignore[no-untyped-call]
                    if remove:
                        pipe.srem(campfire_index(map_id), *sorted(remove))
                    await pipe.execute()
                except WatchError:
                    continue
                else:
                    return

    async def remove(self, map_id: int, x: int, y: int) -> None:
        """Retira una fogata concreta y su referencia en un solo EXEC."""
        key = f"world:campfire:{map_id}:{x}:{y}"
        async with self.redis.redis.pipeline() as pipe:
            pipe.delete(key)
            pipe.srem(campfire_index(map_id), key)
            await pipe.execute()

    async def rebuild(self) -> None:
        """Reconstruye índices antes del listener; conserva hashes y TTL existentes."""
        raw, now = self.redis.redis, time.time()
        async for key in raw.scan_iter(match="world:campfires:*", count=256):
            await raw.delete(key)
        batch: list[str] = []
        async for key in raw.scan_iter(match="world:campfire:*", count=256):
            batch.append(str(key))
            if len(batch) == REBUILD_BATCH:
                await self._rebuild_batch(batch, now)
                batch.clear()
        if batch:
            await self._rebuild_batch(batch, now)

    async def _rebuild_batch(self, keys: list[str], now: float) -> None:
        async with self.redis.redis.pipeline(transaction=False) as pipe:
            for key in keys:
                pipe.hgetall(key)
            rows = cast("list[dict[str, str]]", await pipe.execute())
        async with self.redis.redis.pipeline() as pipe:
            for key, row in zip(keys, rows, strict=True):
                try:
                    map_id = int(key.split(":")[2])
                except ValueError, IndexError:
                    continue
                if _position(key, row, map_id, now) is not None:
                    pipe.sadd(campfire_index(map_id), key)
            await pipe.execute()
