"""Migración reiniciable, con copia por contenedor y época UTC fija."""

import json
import time
from typing import TYPE_CHECKING, cast

from redis.exceptions import WatchError

from src.items import ledger
from src.items.policy import policies
from src.utils.resource_transaction import Decision, Resource, _enqueue_writes, _read_snapshot

if TYPE_CHECKING:
    from redis.asyncio import Redis

PATTERNS = ("player:*:inventory", "bank:*:vault", "merchant:*:inventory", "clan:depot:*")


async def migrate(redis: Redis) -> int:
    """Migra antes de admitir conexiones; reanudar conserva IDs, fechas y originales.

    Un contenedor sin capacidad detiene la puesta en marcha sin borrar objetos.
    Los contenedores ya migrados permanecen verificables y no se rejuvenecen.

    Returns:
        Cantidad de contenedores migrados; cero para un formato ya activo.

    Raises:
        RuntimeError: Si hay sesiones activas al comenzar la migración.
    """
    policies()
    if await redis.get(ledger.FORMAT_KEY) == "1":
        return 0
    async for _owner in redis.scan_iter(match="session:*:owner", count=128):
        message = "Detener las sesiones activas antes de migrar los objetos individuales"
        raise RuntimeError(message)
    await redis.set("items:migration:epoch", str(int(time.time())), nx=True)
    epoch = int(cast("str", await redis.get("items:migration:epoch")))
    count = 0
    for pattern in PATTERNS:
        async for raw_key in redis.scan_iter(match=pattern, count=128):
            key = raw_key.decode() if isinstance(raw_key, bytes) else raw_key
            if not ledger.container(key) or await redis.type(key) != "hash":
                continue
            await _container(redis, Resource(key, "hash"), epoch)
            count += 1
    # El formato del suelo ya fue migrado a hashes por ensure_schema_ready.
    async for raw_key in redis.scan_iter(match="ground_items:*", count=128):
        key = raw_key.decode() if isinstance(raw_key, bytes) else raw_key
        await _container(redis, Resource(key, "ground"), epoch)
        count += 1
    await redis.set(ledger.FORMAT_KEY, "1")
    return count


async def _container(redis: Redis, resource: Resource, epoch: int) -> None:
    backup = "items:migration:backup:" + resource.key
    for _ in range(32):
        async with redis.pipeline() as pipe:
            try:
                await pipe.watch(resource.key, backup)
                snapshot = await _read_snapshot(pipe, (resource,))
                value = snapshot[resource.key]
                original = value.copy() if isinstance(value, dict) else value
                if await pipe.exists(backup):
                    # Un commit previo incluyó el backup y el contenedor juntos.
                    return
                _, refs = await ledger.prepare(pipe, snapshot, (resource,))
                decision, resources = await ledger.finish(
                    pipe,
                    snapshot,
                    (resource,),
                    f"migration-v1:{resource.key}",
                    Decision({"applied": True}, {resource.key: original}),
                    epoch,
                    refs,
                )
                pipe.multi()  # type: ignore[no-untyped-call]
                pipe.set(backup, json.dumps(original, sort_keys=True))
                _enqueue_writes(pipe, {r.key: r for r in resources}, decision.writes)
                await pipe.execute()
            except WatchError:
                continue
            else:
                return
    msg = "No se pudo migrar un contenedor concurrente; detener otros servidores"
    raise RuntimeError(msg)
