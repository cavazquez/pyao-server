"""Commit conjunto de recursos Redis y recibo para resolver respuestas inciertas."""

import asyncio
import json
import random
import time
from collections.abc import Mapping
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
from src.utils.ground_state import GroundState
from src.utils.ground_storage import (
    encode_fields,
    field_position,
    map_id_from_key,
    read_ground,
    validate_fields,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from redis.asyncio import Redis
    from redis.asyncio.client import Pipeline
    from redis.typing import EncodableT

ResourceValue = str | dict[str, str] | set[str] | None
Snapshot = dict[str, ResourceValue]


@dataclass(frozen=True, slots=True)
class Resource:
    """Clave y tipo esperado de un recurso cubierto por WATCH."""

    key: str
    kind: Literal["hash", "string", "set", "ground"]
    ttl_seconds: int | None = None
    keep_ttl: bool = False
    fields: tuple[str, ...] | None = None


@dataclass(frozen=True, slots=True)
class Decision:
    """Resultado serializable y valores completos que se confirman juntos."""

    result: dict[str, Any]
    writes: Mapping[str, str | dict[str, str] | set[str]]


def _request_fingerprint(resources: tuple[Resource, ...], request: dict[str, Any]) -> str:
    return sha256(
        json.dumps(
            {
                "request": request,
                "resources": [
                    (r.key, r.kind, r.fields) if r.kind == "ground" else (r.key, r.kind)
                    for r in resources
                ],
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()


def _receipt_matches(
    receipt: dict[str, Any], resources: tuple[Resource, ...], request: dict[str, Any]
) -> bool:
    """Acepta recibos previos a v6 sin debilitar el alcance de los recibos nuevos.

    Returns:
        Si el recurso y la petición corresponden al commit ya confirmado.
    """
    if receipt["request"] == _request_fingerprint(resources, request):
        return True
    if receipt.get("version") is not None:
        return False
    legacy = tuple(Resource(r.key, "string") if r.kind == "ground" else r for r in resources)
    return bool(receipt["request"] == _request_fingerprint(legacy, request))


async def _read_snapshot(pipe: Pipeline, resources: tuple[Resource, ...]) -> Snapshot:
    """Lee sólo el alcance declarado mientras WATCH protege todas las precondiciones.

    Returns:
        Copias de los recursos sin publicar modificaciones.
    """
    snapshot: Snapshot = {}
    for resource in resources:
        if resource.kind == "ground":
            ground = await read_ground(pipe, map_id_from_key(resource.key), resource.fields)
            snapshot[resource.key] = ground.encode()
        elif resource.kind == "hash":
            snapshot[resource.key] = await cast(
                "Awaitable[dict[str, str]]", pipe.hgetall(resource.key)
            )
        elif resource.kind == "set":
            snapshot[resource.key] = await cast("Awaitable[set[str]]", pipe.smembers(resource.key))
        else:
            value = await pipe.get(resource.key)
            snapshot[resource.key] = value.decode() if isinstance(value, bytes) else value
    return snapshot


async def read_resource_receipt(
    redis: Redis,
    resources: tuple[Resource, ...],
    identity: str,
    request: dict[str, Any],
) -> dict[str, Any] | None:
    """Consulta el resultado sin escribir ni permitir cruces de cuenta/recurso.

    Returns:
        Resultado original o None si no existe un recibo vigente.

    Raises:
        ValueError: Si el ID pertenece a otra petición o no cumple el formato.
    """
    validate_operation_id(identity)
    saved = await redis.get(f"operation:resources:{identity}")
    if saved is None:
        return None
    receipt = json.loads(saved)
    if not _receipt_matches(receipt, resources, request):
        message = "Identificador reutilizado para otra petición"
        raise ValueError(message)
    return cast("dict[str, Any]", receipt["result"])


async def transact(  # ruff: ignore[too-many-statements] - un solo límite de commit para negocio, impuesto y recibo.
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
    # La importación diferida evita un ciclo con Resource/Snapshot, definidos aquí.
    from src.economy.tax_transactions import tax_resources, taxed_decision  # ruff: ignore[import-outside-top-level]
    from src.economy.taxes import utc_day  # ruff: ignore[import-outside-top-level]

    created_at = validate_operation_id(identity)
    fingerprint = _request_fingerprint(resources, request)
    tax_day = utc_day()
    original_resources = resources
    resources = tax_resources(resources, tax_day)
    if any(
        (
            resource.ttl_seconds is not None
            and (type(resource.ttl_seconds) is not int or resource.ttl_seconds < 1)
        )
        or (resource.keep_ttl and resource.ttl_seconds is not None)
        for resource in resources
    ):
        msg = "TTL de recurso inválido"
        raise ValueError(msg)
    by_key = {resource.key: resource for resource in resources}
    for resource in resources:
        if resource.kind == "ground":
            if not map_id_from_key(resource.key):
                msg = "Clave de suelo inválida"
                raise ValueError(msg)
            if resource.fields is not None:
                for field in resource.fields:
                    field_position(field)
                if tuple(sorted(set(resource.fields))) != resource.fields:
                    msg = "Alcance del suelo duplicado o sin normalizar"
                    raise ValueError(msg)
        elif resource.fields is not None:
            msg = "Sólo el suelo permite declarar casillas"
            raise ValueError(msg)
    receipt_key = f"operation:resources:{identity}"
    if len(by_key) != len(resources) or receipt_key in by_key:
        msg = "Recursos duplicados o reservados"
        raise ValueError(msg)
    for attempt in range(MAX_TRANSACTION_ATTEMPTS):
        async with redis.pipeline() as pipe:
            try:
                await pipe.watch(*by_key, receipt_key)
                saved = await pipe.get(receipt_key)
                if saved is not None:
                    receipt = json.loads(saved)
                    if not _receipt_matches(receipt, original_resources, request):
                        msg = "Identificador reutilizado para otra petición"
                        raise ValueError(msg)
                    return cast("dict[str, Any]", receipt["result"])
                age = time.time() - created_at
                if age < -MAX_CLOCK_SKEW_SECONDS or age > retry_window_seconds:
                    msg = "Operación vencida; consultar estado antes de iniciar otra"
                    raise ValueError(msg)
                snapshot = await _read_snapshot(pipe, resources)
                decision = taxed_decision(snapshot, original_resources, tax_day, decide)
                _validate_writes(by_key, decision.writes)
                receipt_json = json.dumps(
                    {"version": 2, "request": fingerprint, "result": decision.result}
                )
                pipe.multi()  # type: ignore[no-untyped-call]
                _enqueue_writes(pipe, by_key, decision.writes)
                pipe.set(receipt_key, receipt_json, ex=receipt_ttl_seconds)
                await pipe.execute()
            except WatchError, RedisConnectionError, RedisTimeoutError:
                await asyncio.sleep(random.uniform(0, min(0.0002 * (attempt + 1), 0.01)))
            else:
                return decision.result
    msg = "Commit no confirmado; conservar el identificador de operación"
    raise RuntimeError(msg)


def _validate_writes(
    resources: dict[str, Resource], writes: Mapping[str, str | dict[str, str] | set[str]]
) -> None:
    """Rechaza toda mutación inválida antes de encolar el primer comando.

    Raises:
        ValueError: Ante clave, tipo, campo o valor fuera del contrato de recursos.
        TypeError: Si una decisión intenta persistir valores de otro tipo.
    """
    for key, value in writes.items():
        if (
            key not in resources
            or (isinstance(value, dict) != (resources[key].kind == "hash"))
            or (isinstance(value, set) != (resources[key].kind == "set"))
        ):
            msg = "La decisión escribió fuera de sus recursos o cambió su tipo"
            raise ValueError(msg)
        if isinstance(value, dict) and not all(
            isinstance(field, str) and isinstance(content, str) for field, content in value.items()
        ):
            msg = "Campos Redis inválidos"
            raise ValueError(msg)
        if isinstance(value, set) and not all(isinstance(member, str) for member in value):
            msg = "Miembros Redis inválidos"
            raise ValueError(msg)
        if not isinstance(value, (str, dict, set)):
            msg = "Valor Redis inválido"
            raise TypeError(msg)
        if resources[key].kind == "ground":
            if not isinstance(value, str):
                msg = "La decisión cambió el formato del suelo"
                raise TypeError(msg)
            state = GroundState(map_id_from_key(key), value)
            validate_fields(state)
            fields = resources[key].fields
            if fields is not None and not state.tiles.keys() <= set(fields):
                msg = "La decisión escribió fuera de las casillas declaradas"
                raise ValueError(msg)


def _enqueue_writes(
    pipe: Pipeline,
    resources: dict[str, Resource],
    writes: Mapping[str, str | dict[str, str] | set[str]],
) -> None:
    """Encola sólo valores previamente validados y sin hacer I/O antes de EXEC."""
    for key, value in writes.items():
        if resources[key].kind == "ground":
            ground = GroundState(map_id_from_key(key), cast("str", value))
            fields = encode_fields(ground)
            present = {field: text for field, text in fields.items() if ground.tiles[field]}
            absent = [field for field in fields if not ground.tiles[field]]
            if present:
                pipe.hset(key, mapping=cast("Mapping[EncodableT, EncodableT]", present))
            if absent:
                pipe.hdel(key, *absent)
        elif isinstance(value, dict) and value:
            pipe.hset(key, mapping=cast("Mapping[EncodableT, EncodableT]", value))
        elif isinstance(value, set):
            pipe.delete(key)
            if value:
                pipe.sadd(key, *sorted(value))
        elif isinstance(value, str):
            if resources[key].keep_ttl:
                pipe.set(key, value, keepttl=True)
            else:
                pipe.set(key, value, ex=resources[key].ttl_seconds)
        ttl = resources[key].ttl_seconds
        if (not isinstance(value, str) or resources[key].kind == "ground") and ttl is not None:
            pipe.expire(key, ttl)
