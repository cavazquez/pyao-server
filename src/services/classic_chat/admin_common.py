"""Primitivas administrativas con auditoría y autorización en el mismo commit."""

import json
import time
from typing import TYPE_CHECKING, Any

from src.services.classic_chat.context import ChatCommandError, ChatContext
from src.utils.gold_atomic import operation_id
from src.utils.resource_transaction import Decision, Resource, Snapshot

MAP_SIDE = 100
SELECTION_RANGE = 10

if TYPE_CHECKING:
    from collections.abc import Callable


async def audited(
    ctx: ChatContext,
    resources: tuple[Resource, ...],
    details: dict[str, Any],
    decide: Callable[[Snapshot], Decision],
) -> dict[str, Any]:
    """Revalida permisos y guarda el cambio y un registro sin argumentos secretos.

    Returns:
        Resultado confirmado.

    Raises:
        ChatCommandError: Si el estado dejó de permitir la operación.
    """
    event = f"moderation:event:{operation_id()}"
    record = json.dumps(
        {"actor": ctx.user, "command": ctx.command, "at": int(time.time()), **details}
    )

    def guarded(snapshot: Snapshot) -> Decision:
        result = decide(snapshot)
        if result.result.get("applied"):
            return Decision(result.result, {**result.writes, event: record})
        return result

    result = await ctx.commit((*resources, Resource(event, "string")), details, guarded)
    if not result.get("applied"):
        message = str(result.get("message", "La operación ya no es válida."))
        raise ChatCommandError(message)
    return result


async def fields(ctx: ChatContext, key: str, values: dict[str, str]) -> None:
    """Escribe campos elegidos por código; ninguna clave proviene del texto libre."""
    await audited(
        ctx,
        (Resource(key, "hash"),),
        {"resource": key, "fields": sorted(values)},
        lambda _snapshot: Decision({"applied": True}, {key: values}),
    )


async def tile(ctx: ChatContext, *, selected: bool = True) -> tuple[int, int, int]:
    """Valida la casilla seleccionada en el mapa actual.

    Returns:
        Mapa y coordenadas dentro de la distancia administrativa visible.

    Raises:
        ChatCommandError: Si el objetivo es remoto, inválido o de otro mapa.
    """
    pos = await ctx.position()
    target = await ctx.read_hash(f"chat:target:{ctx.user}") if selected else {}
    map_id, x, y = (
        int(target.get("map", pos["map"])),
        int(target.get("x", pos["x"])),
        int(target.get("y", pos["y"])),
    )
    if (
        map_id != pos["map"]
        or not ctx.deps.map_manager.has_map(map_id)
        or not 1 <= x <= MAP_SIDE
        or not 1 <= y <= MAP_SIDE
        or max(abs(x - pos["x"]), abs(y - pos["y"])) > SELECTION_RANGE
    ):
        message = "Selecciona una casilla válida del mapa actual."
        raise ChatCommandError(message)
    return map_id, x, y
