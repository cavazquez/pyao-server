"""Reglas administrativas del mapa, evaluadas sobre el snapshot de cada acción."""

import asyncio
import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError

from src.services.combat.pvp_policy import PvpPolicy, is_hostile
from src.utils.redis_config import RedisKeys
from src.utils.resource_transaction import Resource, Snapshot

DUEL_TRIGGER = 6
SAFE_TRIGGER = 4
READ_ATTEMPTS = 3

if TYPE_CHECKING:
    from redis.asyncio import Redis

WORLD_REVISION = "world:map:revision"


@dataclass(frozen=True)
class WorldSnapshot:
    """Reglas coherentes con una revisión; el recibo conserva recursos estables."""

    map_id: int
    revision: str | None
    values: Snapshot

    def merge(self, snapshot: Snapshot, user: int) -> Snapshot | None:
        """Comprueba la revisión observada bajo WATCH antes de usar las reglas.

        Returns:
            Snapshot con reglas de sólo lectura, o None si cambió el mundo.
        """
        position = cast("dict[str, str]", snapshot.get(RedisKeys.player_position(user)) or {})
        if (
            snapshot.get(WORLD_REVISION) != self.revision
            or int(position.get("map", 0)) != self.map_id
        ):
            return None
        return {**snapshot, **self.values}


async def prepare(redis: Redis, user: int) -> WorldSnapshot:
    """Lee revisión, reglas y casillas juntas, antes del commit de una acción.

    Returns:
        Copia coherente del mundo que se revalidará bajo WATCH.

    Raises:
        ConnectionError: Si los datos o precondiciones de la operación son inválidos.
        TimeoutError: Si los datos o precondiciones de la operación son inválidos.
    """
    map_id = int(await redis.hget(RedisKeys.player_position(user), "map") or 0)
    declared = resources(map_id)
    for attempt in range(READ_ATTEMPTS):
        try:
            async with redis.pipeline(transaction=True) as pipe:
                pipe.get(WORLD_REVISION)
                for resource in declared:
                    pipe.hgetall(resource.key)
                revision, *rows = await pipe.execute()
            break
        except RedisConnectionError, RedisTimeoutError:
            if attempt + 1 == READ_ATTEMPTS:
                raise
            # Este EXEC sólo lee. Repetirlo no cobra ni repite ningún efecto.
            await asyncio.sleep(0)
    return WorldSnapshot(
        map_id, revision, {resource.key: row for resource, row in zip(declared, rows, strict=True)}
    )


def resources(map_id: int) -> tuple[Resource, ...]:
    """Declara reglas y casillas del mapa de una intención congelada.

    Returns:
        Recursos que WATCH protegerá junto con el combate o movimiento.
    """
    return (
        Resource(f"world:map:rules:{map_id}", "hash"),
        Resource(f"world:map:tiles:{map_id}", "hash"),
    )


def rules(snapshot: Snapshot, map_id: int) -> dict[str, str]:
    """Lee un mapa ausente como configuración sin overlays.

    Returns:
        Reglas explícitas del mapa.
    """
    return cast("dict[str, str]", snapshot.get(f"world:map:rules:{map_id}") or {})


def trigger(snapshot: Snapshot, position: Mapping[str, str | int]) -> int:
    """Obtiene el trigger de una casilla sin consultar ni recorrer otros mapas.

    Returns:
        Trigger AO de cero a seis.
    """
    rows = cast("dict[str, str]", snapshot.get(f"world:map:tiles:{position.get('map', 0)}") or {})
    tile = json.loads(rows.get(f"{position.get('x', 0)},{position.get('y', 0)}", "{}"))
    return int(tile.get("trigger", 0))


def policy(snapshot: Snapshot, user: int, base: PvpPolicy, *, target: int = 0) -> PvpPolicy:
    """Aplica SEGURO conservando las demás reglas de consentimiento y facciones.

    Returns:
        Política efectiva para este snapshot.
    """
    position = cast("dict[str, str]", snapshot[RedisKeys.player_position(user)])
    map_id = int(position.get("map", 0))
    state = rules(snapshot, map_id)
    safe = set(base.safe_maps)
    if state.get("safe") == "1":
        safe.add(map_id)
    elif state.get("safe") == "0":
        safe.discard(map_id)
    if target and duel(snapshot, user, target):
        safe.discard(map_id)
    return PvpPolicy(base.enabled, tuple(sorted(safe)))


def duel(snapshot: Snapshot, user: int, target: int) -> bool:
    """Distingue una pelea acordada dentro del área de duelo.

    Returns:
        Si ambos personajes están en casillas de duelo del mismo mapa.
    """
    if not target:
        return False
    source = cast("dict[str, str]", snapshot[RedisKeys.player_position(user)])
    other = cast("dict[str, str]", snapshot[RedisKeys.player_position(target)])
    return (
        source.get("map") == other.get("map")
        and trigger(snapshot, source) == DUEL_TRIGGER
        and trigger(snapshot, other) == DUEL_TRIGGER
    )


def combat_rejection(
    snapshot: Snapshot, user: int, target: int, spell: Mapping[str, Any] | None = None
) -> str:
    """Aplica prohibiciones del mapa antes de cobrar recursos.

    Returns:
        Motivo del rechazo, o vacío si el mapa permite la acción.
    """
    source = cast("dict[str, str]", snapshot[RedisKeys.player_position(user)])
    state = rules(snapshot, int(source.get("map", 0)))
    if spell is not None:
        if state.get("no_magic") == "1":
            return "La magia está deshabilitada en este mapa."
        if state.get("no_invisible") == "1" and spell.get("makes_invisible"):
            return "La invisibilidad está deshabilitada en este mapa."
        if state.get("no_revive") == "1" and spell.get("revives"):
            return "La resurrección está deshabilitada en este mapa."
        if state.get("no_summon") == "1" and (spell.get("invokes") or spell.get("warps_pet")):
            return "Las invocaciones están deshabilitadas en este mapa."
    hostile = spell is None or is_hostile(spell)
    if hostile and trigger(snapshot, source) == SAFE_TRIGGER:
        return "No puedes combatir desde una casilla segura."
    if target and hostile:
        other = cast("dict[str, str]", snapshot[RedisKeys.player_position(target)])
        if trigger(snapshot, source) == SAFE_TRIGGER or trigger(snapshot, other) == SAFE_TRIGGER:
            return "No puedes combatir desde una casilla segura."
    return ""
