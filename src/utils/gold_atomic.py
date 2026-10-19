"""Mutaciones condicionales de oro con WATCH y recibo idempotente por operación."""

import asyncio
import json
import random
import re
import time
from dataclasses import asdict, dataclass
from hashlib import sha256
from typing import TYPE_CHECKING, Literal, cast
from uuid import uuid4

from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError
from redis.exceptions import WatchError

from src.models.item_constants import MAX_PLAYER_GOLD

if TYPE_CHECKING:
    from redis.asyncio import Redis

RECEIPT_TTL_SECONDS = 600
RETRY_WINDOW_SECONDS = 300
MAX_TRANSACTION_ATTEMPTS = 256
MAX_CLOCK_SKEW_SECONDS = 5
_OPERATION_ID = re.compile(r"^([0-9]{10,13})\.([0-9a-f]{32})$")


@dataclass(frozen=True, slots=True)
class GoldResult:
    """Saldo y cantidad efectivos del commit, incluidos rechazos identificados."""

    applied: bool
    balance: int
    amount: int
    reason: str = ""


def operation_id() -> str:
    """Genera una identidad con fecha para rechazar replays una vez vencido el recibo.

    Returns:
        Timestamp de servidor y nonce aleatorio, sin datos de la cuenta.
    """
    return f"{int(time.time())}.{uuid4().hex}"


def validate_operation_id(value: str) -> int:
    """Valida una identidad acotada antes de construir claves Redis.

    Returns:
        Fecha de creación en segundos.

    Raises:
        ValueError: Si el identificador no tiene el formato del servidor.
    """
    match = _OPERATION_ID.fullmatch(value)
    if match is None:
        msg = "Identificador de operación inválido"
        raise ValueError(msg)
    return int(match[1])


def calculate_gold(current: int, amount: int, mode: str) -> GoldResult:
    """Calcula el único resultado permitido sin hacer I/O.

    Returns:
        Resultado efectivo o rechazo sin modificación de saldo.

    Raises:
        ValueError: Si el estado persistido está fuera de rango.
    """
    if not 0 <= current <= MAX_PLAYER_GOLD:
        msg = "Saldo persistido de oro fuera de rango"
        raise ValueError(msg)
    if mode == "set":
        return GoldResult(applied=True, balance=amount, amount=amount - current)
    if mode == "capped_credit":
        accepted = min(amount, MAX_PLAYER_GOLD - current)
        return GoldResult(applied=True, balance=current + accepted, amount=accepted)
    if mode == "debit":
        if amount > current:
            return GoldResult(applied=False, balance=current, amount=0, reason="insufficient")
        return GoldResult(applied=True, balance=current - amount, amount=amount)
    if amount > MAX_PLAYER_GOLD - current:
        return GoldResult(applied=False, balance=current, amount=0, reason="overflow")
    return GoldResult(applied=True, balance=current + amount, amount=amount)


async def change_gold(
    redis: Redis,
    key: str,
    amount: int,
    mode: Literal["credit", "debit", "capped_credit", "set"],
    *,
    identity: str | None = None,
) -> GoldResult:
    """Confirma saldo y recibo juntos; un ACK perdido no repite la mutación.

    Returns:
        El mismo resultado para todos los reintentos identificados de esa petición.

    Raises:
        ValueError: Ante cantidad, identidad o replay vencido/diferente inválidos.
        RuntimeError: Si no se logra confirmar tras contención o cortes persistentes.
    """
    if type(amount) is not int or not 0 <= amount <= MAX_PLAYER_GOLD:
        msg = "Cantidad de oro fuera de rango"
        raise ValueError(msg)
    identity = identity or operation_id()
    from src.economy.tax_transactions import stamp_money_revision, tax_resources, tax_snapshot  # ruff: ignore[import-outside-top-level]
    from src.economy.taxes import utc_day  # ruff: ignore[import-outside-top-level]
    from src.utils.resource_transaction import Resource, Snapshot, _enqueue_writes  # ruff: ignore[import-outside-top-level]

    today = utc_day()
    resources = tax_resources((Resource(key, "hash"),), today)
    created_at = validate_operation_id(identity)
    receipt_key = f"operation:gold:{key}:{identity}"
    fingerprint = sha256(f"{key}\0{mode}\0{amount}".encode()).hexdigest()
    for attempt in range(MAX_TRANSACTION_ATTEMPTS):
        async with redis.pipeline() as pipe:
            try:
                await pipe.watch(*(resource.key for resource in resources), receipt_key)
                saved = await pipe.get(receipt_key)
                if saved is not None:
                    receipt = json.loads(saved)
                    if receipt["request"] != fingerprint:
                        msg = "Identificador reutilizado para otra petición"
                        raise ValueError(msg)
                    return GoldResult(**receipt["result"])
                age = time.time() - created_at
                if age < -MAX_CLOCK_SKEW_SECONDS or age > RETRY_WINDOW_SECONDS:
                    msg = "Operación vencida; consultar el saldo antes de iniciar otra"
                    raise ValueError(msg)
                snapshot: Snapshot = {}
                for resource in resources:
                    snapshot[resource.key] = (
                        cast("dict[str, str]", await pipe.hgetall(resource.key))
                        if resource.kind == "hash"
                        else cast("str | None", await pipe.get(resource.key))
                    )
                projected, writes = tax_snapshot(snapshot, (Resource(key, "hash"),), today)
                current = int(cast("dict[str, str]", projected[key]).get("gold", 0))
                result = calculate_gold(current, amount, mode)
                if result.applied and result.balance != current:
                    writes[key] = {
                        **cast("dict[str, str]", writes.get(key, {})),
                        "gold": str(result.balance),
                    }
                pipe.multi()  # type: ignore[no-untyped-call]
                _enqueue_writes(
                    pipe,
                    {resource.key: resource for resource in resources},
                    stamp_money_revision(snapshot, (Resource(key, "hash"),), writes),
                )
                pipe.set(
                    receipt_key,
                    json.dumps({"request": fingerprint, "result": asdict(result)}),
                    ex=RECEIPT_TTL_SECONDS,
                )
                await pipe.execute()
            except WatchError, RedisConnectionError, RedisTimeoutError:
                # Releer el recibo resuelve también el resultado incierto de EXEC.
                await asyncio.sleep(random.uniform(0, min(0.0002 * (attempt + 1), 0.01)))
            else:
                return result
    msg = "No se pudo confirmar la mutación de oro; conservar su identificador"
    raise RuntimeError(msg)
