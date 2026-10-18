"""Contrato de esquema persistido y puerta de arranque antes de cargar seeds."""

from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from collections.abc import Awaitable

    from redis.asyncio import Redis

SCHEMA_KEY = "schema:state"
MIGRATION_LOCK_KEY = "schema:migration:lock"
CURRENT_SCHEMA_VERSION = 2
MIGRATIONS = {1: "adopt-legacy-layout", 2: "normalize-mana-int16"}


class SchemaMigrationError(RuntimeError):
    """El estado requiere una migración explícita o tiene una versión incompatible."""


def parse_version(value: str | bytes | None) -> int:
    """Valida la versión sin sustituir un valor inválido o futuro por defaults.

    Returns:
        Versión conocida, o cero para el layout legado sin versionar.

    Raises:
        SchemaMigrationError: Si el valor es inválido o más nuevo que este servidor.
    """
    if value is None:
        return 0
    try:
        version = int(value)
    except ValueError, TypeError:
        msg = "La versión del esquema Redis es inválida"
        raise SchemaMigrationError(msg) from None
    if version < 0 or version > CURRENT_SCHEMA_VERSION:
        msg = "El esquema Redis es incompatible con esta versión del servidor"
        raise SchemaMigrationError(msg)
    return version


async def ensure_schema_ready(redis: Redis) -> None:
    """Aborta antes de seeds para datos legados, migraciones activas o versiones futuras.

    Una base nueva sólo adopta el esquema actual si no contiene estado fuera de
    los defaults de infraestructura. Nunca reescribe cuentas, economía o progreso.

    Raises:
        SchemaMigrationError: Si se requiere migración o hay otro proceso migrando.
    """
    if await redis.exists(MIGRATION_LOCK_KEY):
        msg = "Hay una migración Redis en curso; esperar su finalización"
        raise SchemaMigrationError(msg)
    value = await cast("Awaitable[str | bytes | None]", redis.hget(SCHEMA_KEY, "version"))
    version = parse_version(value)
    if version == CURRENT_SCHEMA_VERSION:
        return
    if value is None:
        async for key in redis.scan_iter():
            name = key.decode() if isinstance(key, bytes) else key
            if not name.startswith(("config:", "server:")):
                break
        else:
            await cast(
                "Awaitable[bool]", redis.hsetnx(SCHEMA_KEY, "version", str(CURRENT_SCHEMA_VERSION))
            )
            parse_version(
                await cast("Awaitable[str | bytes | None]", redis.hget(SCHEMA_KEY, "version"))
            )
            return
    msg = (
        "Estado Redis legado: crear/verificar backup y ejecutar "
        "uv run python -m src.operations.redis_schema migrate --backup <archivo.rdb>"
    )
    raise SchemaMigrationError(msg)
