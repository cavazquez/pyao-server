"""Suelo v2: un hash por mapa, con una lista JSON por casilla canónica."""

import json
from collections.abc import Iterable, Mapping
from itertools import starmap
from typing import TYPE_CHECKING, cast

from src.utils.ground_state import (
    MAX_GROUND_COORDINATE,
    MAX_GROUND_ITEMS_PER_TILE,
    MAX_GROUND_MAP_ID,
    GroundState,
)
from src.utils.redis_config import RedisKeys

if TYPE_CHECKING:
    from collections.abc import Awaitable

    from redis.asyncio import Redis
    from redis.asyncio.client import Pipeline

GROUND_BATCH_SIZE = 64
KEY_PARTS = 2
COORDINATE_PARTS = 2


def map_id_from_key(key: str) -> int:
    """Reconoce sólo claves canónicas del suelo.

    Returns:
        ID del mapa, o cero para un recurso ajeno.
    """
    parts = key.split(":")
    if len(parts) != KEY_PARTS or parts[0] != "ground_items" or not parts[1].isdigit():
        return 0
    map_id = int(parts[1])
    return map_id if 1 <= map_id <= MAX_GROUND_MAP_ID and str(map_id) == parts[1] else 0


def position_field(x: int, y: int) -> str:
    """Codifica una casilla sin admitir alias, booleanos o coordenadas externas.

    Returns:
        Campo canónico x,y.

    Raises:
        ValueError: Si la casilla no pertenece al mapa.
    """
    if any(type(value) is not int or not 1 <= value <= MAX_GROUND_COORDINATE for value in (x, y)):
        message = "Coordenada del suelo inválida"
        raise ValueError(message)
    return f"{x},{y}"


def field_position(field: str) -> tuple[int, int]:
    """Valida la representación de una casilla persistida.

    Returns:
        Coordenadas canónicas de la casilla.

    Raises:
        ValueError: Si hay alias o una coordenada inválida.
    """
    parts = field.split(",")
    if len(parts) == COORDINATE_PARTS and all(part.isdigit() for part in parts):
        x, y = (int(part) for part in parts)
        if position_field(x, y) == field:
            return x, y
    message = "Campo de suelo no canónico"
    raise ValueError(message)


def position_fields(positions: Iterable[tuple[int, int]]) -> tuple[str, ...]:
    """Normaliza el alcance de lectura y escritura de una operación.

    Returns:
        Campos únicos y ordenados, también para fingerprints de replay.
    """
    return tuple(sorted(set(starmap(position_field, positions))))


def decode_fields(map_id: int, values: Mapping[str, str]) -> GroundState:
    """Reconstruye exclusivamente los campos leídos sin interpretar otros tiles.

    Returns:
        Estado validado con identidades y metadatos completos.
    """
    for field in values:
        field_position(field)
    state = GroundState.from_tiles(
        map_id, {field: json.loads(value) for field, value in values.items()}
    )
    validate_fields(state)
    return state


def validate_fields(state: GroundState) -> None:
    """Valida el límite por casilla sin truncar ni fusionar objetos existentes.

    Raises:
        ValueError: Si hay alias de coordenadas o una casilla excede su capacidad.
    """
    for coordinate, items in state.tiles.items():
        field_position(coordinate)
        if len(items) > MAX_GROUND_ITEMS_PER_TILE:
            message = "Casilla de suelo por encima de su capacidad"
            raise ValueError(message)


def encode_fields(state: GroundState) -> dict[str, str]:
    """Codifica las listas sin volver a serializar los demás tiles del mapa.

    Returns:
        Campos completos, incluyendo listas vacías para HDEL.
    """
    validate_fields(state)
    return {
        field: json.dumps(items, ensure_ascii=True, separators=(",", ":"))
        for field, items in state.tiles.items()
    }


async def read_ground(
    redis: Redis | Pipeline, map_id: int, fields: tuple[str, ...] | None = None
) -> GroundState:
    """Lee HMGET para acciones; reserva HGETALL para cargar el mapa completo.

    Returns:
        Copia del alcance solicitado, validada antes de planificar cambios.
    """
    key = RedisKeys.ground_items(map_id)
    if fields is None:
        values = await cast("Awaitable[dict[str, str]]", redis.hgetall(key))
    elif fields:
        rows = await cast("Awaitable[list[str | None]]", redis.hmget(key, list(fields)))
        values = {
            field: value for field, value in zip(fields, rows, strict=True) if value is not None
        }
    else:
        values = {}
    return decode_fields(map_id, values)
