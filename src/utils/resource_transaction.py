"""Commit conjunto de recursos Redis y recibo para resolver respuestas inciertas."""

import asyncio
import json
import random
import time
from dataclasses import dataclass
from hashlib import sha256
from typing import TYPE_CHECKING, Any, Literal, cast

from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError
from redis.exceptions import WatchError

from src.utils.gold_atomic import (
    MAX_CLOCK_SKEW_SECONDS,
    MAX_TRANSACTION_ATTEMPTS,
    RECEIPT_TTL_SECONDS,
    RETRY_WINDOW_SECONDS,
    validate_operation_id,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from redis.asyncio import Redis

ResourceValue = str | dict[str, str] | None
Snapshot = dict[str, ResourceValue]


@dataclass(frozen=True, slots=True)
class Resource:
    """Clave y tipo esperado de un recurso cubierto por WATCH."""

    key: str
    kind: Literal["hash", "string"]
    ttl_seconds: int | None = None


@dataclass(frozen=True, slots=True)
class Decision:
    """Resultado serializable y valores completos que se confirman juntos."""

    result: dict[str, Any]
    writes: dict[str, str | dict[str, str]]


async def transact(
    redis: Redis,
    resources: tuple[Resource, ...],
    identity: str,
    request: dict[str, Any],
    decide: Callable[[Snapshot], Decision],
    *,
    receipt_ttl_seconds: int = RECEIPT_TTL_SECONDS,
    retry_window_seconds: int = RETRY_WINDOW_SECONDS,
) -> dict[str, Any]:
    """Lee precondiciones y confirma todos los cambios con su recibo en un EXEC.

    Las funciones de decisión no hacen I/O ni escriben fuera de esta transacción.
    Todas las claves que modifican deben estar declaradas entre los recursos.

    Returns:
        El resultado confirmado, idéntico en un reintento con el mismo ID y petición.

    Raises:
        ValueError: Por identidad vencida/reutilizada, claves o campos inválidos.
        RuntimeError: Si no puede determinar el commit tras reintentos acotados.
    """
    if (
        retry_window_seconds < 1
        or receipt_ttl_seconds <= retry_window_seconds + MAX_CLOCK_SKEW_SECONDS
    ):
        msg = "Retención del recibo insuficiente para la ventana de reintento"
        raise ValueError(msg)
    created_at = validate_operation_id(identity)
    if any(
        resource.ttl_seconds is not None
        and (type(resource.ttl_seconds) is not int or resource.ttl_seconds < 1)
        for resource in resources
    ):
        msg = "TTL de recurso inválido"
        raise ValueError(msg)
    by_key = {resource.key: resource for resource in resources}
    receipt_key = f"operation:resources:{identity}"
    if len(by_key) != len(resources) or receipt_key in by_key:
        msg = "Recursos duplicados o reservados"
        raise ValueError(msg)
    fingerprint = sha256(
        json.dumps(
            {"request": request, "resources": [(r.key, r.kind) for r in resources]},
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    for attempt in range(MAX_TRANSACTION_ATTEMPTS):
        async with redis.pipeline() as pipe:
            try:
                await pipe.watch(*by_key, receipt_key)
                saved = await pipe.get(receipt_key)
                if saved is not None:
                    receipt = json.loads(saved)
                    if receipt["request"] != fingerprint:
                        msg = "Identificador reutilizado para otra petición"
                        raise ValueError(msg)
                    return cast("dict[str, Any]", receipt["result"])
                age = time.time() - created_at
                if age < -MAX_CLOCK_SKEW_SECONDS or age > retry_window_seconds:
                    msg = "Operación vencida; consultar estado antes de iniciar otra"
                    raise ValueError(msg)
                snapshot: Snapshot = {}
                for resource in resources:
                    if resource.kind == "hash":
                        snapshot[resource.key] = await cast(
                            "Awaitable[dict[str, str]]", pipe.hgetall(resource.key)
                        )
                    else:
                        snapshot[resource.key] = await pipe.get(resource.key)
                decision = decide(snapshot)
                _validate_writes(by_key, decision.writes)
                receipt_json = json.dumps({"request": fingerprint, "result": decision.result})
                pipe.multi()  # type: ignore[no-untyped-call]
                for key, value in decision.writes.items():
                    if isinstance(value, dict) and value:
                        pipe.hset(key, mapping=value)
                    elif isinstance(value, str):
                        pipe.set(key, value, ex=by_key[key].ttl_seconds)
                pipe.set(receipt_key, receipt_json, ex=receipt_ttl_seconds)
                await pipe.execute()
            except WatchError, RedisConnectionError, RedisTimeoutError:
                await asyncio.sleep(random.uniform(0, min(0.0002 * (attempt + 1), 0.01)))
            else:
                return decision.result
    msg = "Commit no confirmado; conservar el identificador de operación"
    raise RuntimeError(msg)


def _validate_writes(
    resources: dict[str, Resource], writes: dict[str, str | dict[str, str]]
) -> None:
    """Rechaza toda mutación inválida antes de encolar el primer comando.

    Raises:
        ValueError: Ante clave, tipo, campo o valor fuera del contrato de recursos.
        TypeError: Si una decisión intenta persistir valores de otro tipo.
    """
    for key, value in writes.items():
        if key not in resources or (isinstance(value, dict) != (resources[key].kind == "hash")):
            msg = "La decisión escribió fuera de sus recursos o cambió su tipo"
            raise ValueError(msg)
        if isinstance(value, dict) and not all(
            isinstance(field, str) and isinstance(content, str) for field, content in value.items()
        ):
            msg = "Campos Redis inválidos"
            raise ValueError(msg)
        if not isinstance(value, (str, dict)):
            msg = "Valor Redis inválido"
            raise TypeError(msg)
