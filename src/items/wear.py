"""Usos cobrados exclusivamente por acciones aceptadas dentro de su EXEC."""

from collections.abc import Mapping
from typing import TYPE_CHECKING, cast

from src.items.condition import condition
from src.items.ledger import PREFIX
from src.utils.inventory_slot import InventorySlot
from src.utils.redis_config import RedisKeys

if TYPE_CHECKING:
    from collections.abc import Iterable

    from src.utils.resource_transaction import Snapshot


def instance(snapshot: Snapshot, user: int, layer: str) -> str:
    """Obtiene la identidad de una pieza observada; vacío para datos aún sin migrar.

    Returns:
        Estado validado de la operación, sin alterar los datos del catálogo.
    """
    gear = cast("dict[str, str]", snapshot[RedisKeys.player_equipment(user)])
    bag = cast("dict[str, str]", snapshot[RedisKeys.player_inventory(user)])
    stack = InventorySlot.parse(bag.get(f"slot_{gear.get(layer, '0')}", ""))
    return stack.instance_ids[0] if stack and stack.instance_ids else ""


def broken(snapshot: Mapping[str, object], iid: str) -> bool:
    """Usa el reloj creciente del mismo snapshot para rechazar herramientas agotadas.

    Returns:
        Estado validado de la operación, sin alterar los datos del catálogo.
    """
    state = snapshot.get(PREFIX + iid)
    return bool(isinstance(state, dict) and condition(state, int(str(snapshot["items:now"])))[2])


def costs(snapshot: Snapshot, user: int, layers: tuple[str, ...]) -> dict[str, int]:
    """Retorna los usos a incluir en el recibo; límites cero no acumulan escrituras.

    Returns:
        Estado validado de la operación, sin alterar los datos del catálogo.
    """
    result = {}
    for layer in layers:
        iid = instance(snapshot, user, layer)
        state = snapshot.get(PREFIX + iid)
        if isinstance(state, dict) and int(state["max_uses"]) and not broken(snapshot, iid):
            result[iid] = 1
    return result


def defensive(snapshot: Snapshot, user: int, *, dodged: bool, blocked: bool) -> dict[str, int]:
    """Un escudo gasta uso al bloquear y la protección al recibir un impacto.

    Returns:
        Estado validado de la operación, sin alterar los datos del catálogo.
    """
    return costs(
        snapshot, user, ("shield",) if blocked else () if dodged else ("armor", "helmet", "boots")
    )


def tool_costs(
    snapshot: Snapshot, stacks: Iterable[InventorySlot], allowed: tuple[int, ...], quantity: int
) -> dict[str, int]:
    """Elige una herramienta utilizable para todo el lote, sin cobrar parcialmente.

    Returns:
        Usos que deben confirmarse con materiales y producto.

    Raises:
        ValueError: Si las herramientas están rotas o no alcanzan los usos del lote.
    """
    if not allowed:
        return {}
    for stack in stacks:
        if stack.item_id not in allowed:
            continue
        if not stack.instance_ids:
            return {}
        iid = stack.instance_ids[0]
        state = cast("dict[str, str]", snapshot[PREFIX + iid])
        maximum = int(state["max_uses"])
        if not broken(snapshot, iid) and (
            not maximum or maximum - int(state["uses_spent"]) >= quantity
        ):
            return {iid: quantity} if maximum else {}
    message = "La herramienta está rota o no tiene usos suficientes para ese lote."
    raise ValueError(message)
