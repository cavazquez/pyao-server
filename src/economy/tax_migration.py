"""Adopción fiscal explícita: ninguna moneda se descuenta al migrar."""

from decimal import Decimal
from typing import TYPE_CHECKING, cast

from src.economy.taxes import DEFAULT_RATE_BPS, TAX_POLICY_KEY, utc_day

if TYPE_CHECKING:
    from collections.abc import Mapping

    from redis.asyncio import Redis as AsyncRedis
    from redis.typing import EncodableT

    from redis import Redis


def tax_repairs(client: Redis, day: int) -> dict[str, dict[str, str]]:
    """Prepara marcadores para saldos heredados.

    Returns:
        Campos fiscales iniciales sin penalizaciones anteriores.
    """
    result = {
        TAX_POLICY_KEY: {
            "version": "1",
            "activation_day": str(day),
            "enabled": "1",
            "rate_bps": str(DEFAULT_RATE_BPS),
        }
    }
    for key in client.scan_iter(match="player:*:user_stats", count=128):
        name = key.decode() if isinstance(key, bytes) else key
        user_id = int(name.split(":")[1])
        result[f"tax:{user_id}:state"] = {
            "version": "1",
            "last_day": str(day),
            "remainder": "0",
            "total_paid": "0",
        }
    return result


async def initialize_tax_policy(redis: AsyncRedis, *, enabled: bool, percentage: float) -> None:
    """Adopta la política en una base nueva.

    Raises:
        ValueError: Si la tasa no es representable o difiere de la política persistida.
    """
    rate = Decimal(str(percentage)) * 100
    if rate != rate.to_integral_value():
        message = "El impuesto admite como máximo dos decimales porcentuales"
        raise ValueError(message)
    rate_bps = int(rate)
    fields = {
        "version": "1",
        "activation_day": str(utc_day()),
        "enabled": "1" if enabled else "0",
        "rate_bps": str(rate_bps),
    }
    # HSETNX de la versión reclama una inicialización completa mediante WATCH.
    from redis.exceptions import WatchError  # ruff: ignore[import-outside-top-level]

    while True:
        async with redis.pipeline() as pipe:
            try:
                await pipe.watch(TAX_POLICY_KEY)
                existing = await pipe.hgetall(TAX_POLICY_KEY)
                if existing:
                    if any(
                        existing.get(k) != fields[k] for k in ("version", "enabled", "rate_bps")
                    ):
                        message = (
                            "La política fiscal persistida difiere del TOML; "
                            "requiere migración explícita"
                        )
                        raise ValueError(message)
                    return
                pipe.multi()  # type: ignore[no-untyped-call]
                pipe.hset(TAX_POLICY_KEY, mapping=cast("Mapping[EncodableT, EncodableT]", fields))
                await pipe.execute()
            except WatchError:
                continue
            else:
                return
