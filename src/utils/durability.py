"""Barrera de AOF sobre una conexión dedicada antes de anunciar commits críticos."""

from contextlib import aclosing
from typing import TYPE_CHECKING
from uuid import uuid4

if TYPE_CHECKING:
    from redis.asyncio import Redis

AOF_TIMEOUT_MS = 5000
BARRIER_TTL_SECONDS = 60


async def ensure_aof(redis: Redis) -> None:
    """Comprueba AOF antes de mutar sin esperar fsync de una escritura artificial.

    La barrera posterior al EXEC sigue siendo obligatoria antes de publicar.

    Raises:
        RuntimeError: Si AOF está deshabilitado o su última escritura falló.
    """
    info = await redis.info("persistence")
    if info.get("aof_enabled") != 1 or info.get("aof_last_write_status") != "ok":
        msg = "Se requiere Redis con AOF activo y sin errores de escritura"
        raise RuntimeError(msg)


async def require_durable(redis: Redis) -> None:
    """Exige fsync local de todos los writes anteriores en el orden de Redis.

    La conexión exclusiva escribe una barrera después de EXEC y ejecuta WAITAOF
    sobre esa misma conexión. No depende de qué conexión devolvió el pool tras EXEC.

    Raises:
        RuntimeError: Si Redis no confirma la persistencia local dentro del plazo.
    """
    # Redis.__aenter__ no libera una conexión si initialize recibe CancelledError.
    # Registrar primero el cierre también cubre una desconexión durante la entrada.
    async with aclosing(redis.client()) as connection:
        await connection.initialize()
        await connection.set(f"durability:barrier:{uuid4().hex}", "1", ex=BARRIER_TTL_SECONDS)
        response = await connection.execute_command("WAITAOF", 1, 0, AOF_TIMEOUT_MS)  # type: ignore[no-untyped-call]
        if not response or response[0] != 1:
            msg = "Commit registrado pero persistencia AOF todavía no confirmada"
            raise RuntimeError(msg)
