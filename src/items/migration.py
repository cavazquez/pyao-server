"""Migración reiniciable, con copia por contenedor y época UTC fija."""

import json
import time
from collections import defaultdict
from collections.abc import Mapping
from typing import TYPE_CHECKING, cast

from redis.asyncio import Redis
from redis.exceptions import WatchError

from src.items import ledger
from src.items.policy import policies
from src.utils.resource_transaction import Decision, Resource, _enqueue_writes, _read_snapshot

if TYPE_CHECKING:
    from redis.asyncio.client import Pipeline

    from src.utils.resource_transaction import Snapshot

PATTERNS = ("player:*:inventory", "bank:*:vault", "merchant:*:inventory", "clan:depot:*")
INSTANCE_BATCH = 1000
BOOTSTRAP_SOCKET_TIMEOUT = 60.0
CREATE_INSTANCES = f"""
for _,key in ipairs(KEYS) do
    redis.call('HSET', key, 'id', string.sub(key, {len(ledger.PREFIX) + 1}), unpack(ARGV))
end
return #KEYS
"""


def _enqueue_migration(
    pipe: Pipeline,
    resources: tuple[Resource, ...],
    snapshot: Snapshot,
    writes: Mapping[str, str | dict[str, str] | set[str] | None],
) -> None:
    """Comparte campos de unidades nuevas sin separar el EXEC de su contenedor."""
    groups: dict[tuple[tuple[str, str], ...], list[str]] = defaultdict(list)
    remaining = dict(writes)
    for key, state in writes.items():
        if (
            key.startswith(ledger.PREFIX)
            and not snapshot.get(key)
            and isinstance(state, dict)
            and state.get("id") == key.removeprefix(ledger.PREFIX)
        ):
            common = tuple(
                sorted((field, value) for field, value in state.items() if field != "id")
            )
            groups[common].append(key)
            remaining.pop(key)
    _enqueue_writes(pipe, {r.key: r for r in resources}, remaining)
    for common, keys in groups.items():
        fields = [value for pair in common for value in pair]
        for offset in range(0, len(keys), INSTANCE_BATCH):
            batch = keys[offset : offset + INSTANCE_BATCH]
            pipe.eval(CREATE_INSTANCES, len(batch), *batch, *fields)


async def migrate(redis: Redis) -> int:
    """Migra antes de admitir conexiones; reanudar conserva IDs, fechas y originales.

    Un contenedor sin capacidad detiene la puesta en marcha sin borrar objetos.
    Los contenedores ya migrados permanecen verificables y no se rejuvenecen.

    Returns:
        Cantidad de contenedores migrados; cero para un formato ya activo.

    """
    policies()
    if await redis.get(ledger.FORMAT_KEY) == "1":
        return 0
    # La creación inicial de miles de unidades comparte un EXEC grande. Usar
    # una conexión propia evita que ese arranque cambie el timeout del juego.
    settings = dict(redis.connection_pool.connection_kwargs)
    timeout = settings.get("socket_timeout")
    if timeout is not None:
        settings["socket_timeout"] = max(float(timeout), BOOTSTRAP_SOCKET_TIMEOUT)
    pool = type(redis.connection_pool)(
        connection_class=redis.connection_pool.connection_class,
        max_connections=1,
        **settings,
    )
    async with Redis.from_pool(pool) as bootstrap:
        return await _migrate(bootstrap)


async def _migrate(redis: Redis) -> int:
    """Aplica los contenedores con una conexión de arranque, antes de admitir sesiones.

    Returns:
        Cantidad de contenedores migrados.

    Raises:
        RuntimeError: Si hay sesiones activas al comenzar la migración.
    """
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
                _enqueue_migration(pipe, resources, snapshot, decision.writes)
                await pipe.execute()
            except WatchError:
                continue
            else:
                return
    msg = "No se pudo migrar un contenedor concurrente; detener otros servidores"
    raise RuntimeError(msg)
