"""Liquidación durable de un intercambio completo, sin escrow ni compensaciones."""

import json
from dataclasses import asdict, dataclass
from hashlib import sha256
from typing import TYPE_CHECKING, Any, cast

from src.economy.devaluation_fractions import move_gold_remainder
from src.models.item_constants import MAX_PLAYER_GOLD
from src.utils.durability import require_durable
from src.utils.gold_atomic import operation_id, validate_operation_id
from src.utils.redis_config import RedisKeys
from src.utils.resource_transaction import Decision, Resource, Snapshot, transact
from src.utils.slot_plan import SlotPlan

if TYPE_CHECKING:
    from collections.abc import Awaitable

    from redis.asyncio import Redis


@dataclass(frozen=True, slots=True)
class OfferedItem:
    """Oferta congelada antes del primer await del commit."""

    slot: int
    item_id: int
    quantity: int


@dataclass(frozen=True, slots=True)
class ParticipantOffer:
    """Participante y recursos cuya identidad se comprueba en el commit."""

    user_id: int
    gold: int
    items: tuple[OfferedItem, ...]


def _plan(
    snapshot: Snapshot,
    offers: tuple[ParticipantOffer, ParticipantOffer],
    capacity: int,
    max_stack: int,
) -> dict[str, str | dict[str, str] | set[str]]:
    """Valida ambos propietarios y calcula el intercambio completo.

    Returns:
        Todos los campos a persistir, o ningún cambio si se lanza una excepción.

    Raises:
        ValueError: Si faltan recursos, hay equipo ofrecido, overflow o espacio insuficiente.
    """
    inventories: dict[int, SlotPlan] = {}
    balances: dict[int, int] = {}
    moved: dict[tuple[int, int], tuple[str, ...]] = {}
    for offer in offers:
        if not 0 <= offer.gold <= MAX_PLAYER_GOLD:
            msg = "Oferta de oro inválida"
            raise ValueError(msg)
        inventory = cast("dict[str, str]", snapshot[RedisKeys.player_inventory(offer.user_id)])
        inventories[offer.user_id] = SlotPlan(inventory, capacity, max_stack)
        stats = cast("dict[str, str]", snapshot[RedisKeys.player_user_stats(offer.user_id)])
        balance = int(stats.get("gold", 0))
        if not 0 <= balance <= MAX_PLAYER_GOLD or balance < offer.gold:
            msg = "No tienes suficiente oro disponible"
            raise ValueError(msg)
        balances[offer.user_id] = balance - offer.gold
        equipment = cast("dict[str, str]", snapshot[RedisKeys.player_equipment(offer.user_id)])
        if any(str(item.slot) in equipment.values() for item in offer.items):
            msg = "Desequipá los objetos antes de intercambiarlos"
            raise ValueError(msg)
        for item in offer.items:
            removed = inventories[offer.user_id].take(item.slot, item.item_id, item.quantity)
            moved[offer.user_id, item.slot] = removed.instance_ids
    for index, offer in enumerate(offers):
        target = offers[1 - index].user_id
        balances[target] += offer.gold
        if balances[target] > MAX_PLAYER_GOLD:
            msg = "El destinatario supera el tope de oro"
            raise ValueError(msg)
        for item in offer.items:
            inventories[target].give(
                item.item_id, item.quantity, instance_ids=moved[offer.user_id, item.slot]
            )
    writes: dict[str, str | dict[str, str] | set[str]] = {}
    for user_id, planned_inventory in inventories.items():
        writes[RedisKeys.player_inventory(user_id)] = planned_inventory.fields()
        writes[RedisKeys.player_user_stats(user_id)] = {"gold": str(balances[user_id])}
    if offers[0].gold > offers[1].gold:
        move_gold_remainder(
            snapshot, offers[0].user_id, offers[1].user_id, offers[0].gold - offers[1].gold, writes
        )
    elif offers[1].gold > offers[0].gold:
        move_gold_remainder(
            snapshot, offers[1].user_id, offers[0].user_id, offers[1].gold - offers[0].gold, writes
        )
    return writes


async def settle_trade(
    redis: Redis,
    identity: str,
    offers: tuple[ParticipantOffer, ParticipantOffer],
    capacity: int,
    max_stack: int,
) -> dict[str, Any]:
    """Confirma inventarios, oro y journal, y exige fsync antes de responder éxito.

    Returns:
        Resultado durable consultable con el mismo ID incluso después de reiniciar.

    Raises:
        ValueError: Ante identidad, participantes o reutilización de una petición distintos.
    """
    validate_operation_id(identity)
    if offers[0].user_id == offers[1].user_id or any(offer.user_id < 1 for offer in offers):
        msg = "Participantes inválidos"
        raise ValueError(msg)
    request = {
        "offers": [asdict(offer) for offer in offers],
        "capacity": capacity,
        "max_stack": max_stack,
    }
    fingerprint = sha256(json.dumps(request, sort_keys=True).encode()).hexdigest()
    journal_key = f"trade:settlement:{identity}"
    # El journal inmutable permite recuperar recibos temporales ya vencidos.
    saved = await cast("Awaitable[dict[str, str]]", redis.hgetall(journal_key))
    if saved:
        if saved["request"] != fingerprint:
            msg = "Identificador reutilizado para otra oferta"
            raise ValueError(msg)
        result = cast("dict[str, Any]", json.loads(saved["result"]))
    else:
        await require_durable(redis)  # Rechaza Redis sin AOF antes de modificar recursos.
        resources = (
            *tuple(
                Resource(key, "hash")
                for offer in offers
                for key in (
                    RedisKeys.player_user_stats(offer.user_id),
                    RedisKeys.player_inventory(offer.user_id),
                    RedisKeys.player_equipment(offer.user_id),
                )
            ),
            Resource(journal_key, "hash"),
        )

        def decide(snapshot: Snapshot) -> Decision:
            journal = cast("dict[str, str]", snapshot[journal_key])
            if journal:
                if journal["request"] != fingerprint:
                    msg = "Identificador reutilizado para otra oferta"
                    raise ValueError(msg)
                return Decision(cast("dict[str, Any]", json.loads(journal["result"])), {})
            try:
                writes = _plan(snapshot, offers, capacity, max_stack)
            except ValueError as error:
                result = {"applied": False, "message": str(error)}
                writes = {}
            else:
                result = {"applied": True, "message": "Intercambio completado."}
            writes[journal_key] = {
                "request": fingerprint,
                "result": json.dumps(result),
                "participants": json.dumps([offer.user_id for offer in offers]),
            }
            return Decision(result, writes)

        result = await transact(redis, resources, identity, request, decide)
    await require_durable(redis)
    return result


async def get_trade_result(redis: Redis, identity: str, user_id: int) -> dict[str, Any] | None:
    """Recupera el resultado confirmado para un participante después de reiniciar.

    Returns:
        Resultado durable si existe y el usuario participó, o None en otro caso.
    """
    validate_operation_id(identity)
    journal = await cast("Awaitable[dict[str, str]]", redis.hgetall(f"trade:settlement:{identity}"))
    if not journal or user_id not in json.loads(journal["participants"]):
        return None
    await require_durable(redis)
    return cast("dict[str, Any]", json.loads(journal["result"]))


async def cancel_settlement(
    redis: Redis,
    identity: str,
    offers: tuple[ParticipantOffer, ParticipantOffer],
    capacity: int,
    max_stack: int,
    reason: str,
) -> dict[str, Any]:
    """Arbitra cancelación versus commit mediante el mismo journal inmutable.

    Returns:
        El resultado ganador; nunca compensa un intercambio ya confirmado.
    """
    validate_operation_id(identity)
    request = {
        "offers": [asdict(offer) for offer in offers],
        "capacity": capacity,
        "max_stack": max_stack,
    }
    fingerprint = sha256(json.dumps(request, sort_keys=True).encode()).hexdigest()
    key = f"trade:settlement:{identity}"

    def decide(snapshot: Snapshot) -> Decision:
        saved = cast("dict[str, str]", snapshot[key])
        if saved:
            if saved["request"] != fingerprint:
                message = "Identificador reutilizado para otra oferta"
                raise ValueError(message)
            return Decision(cast("dict[str, Any]", json.loads(saved["result"])), {})
        result = {"applied": False, "cancelled": True, "message": reason}
        return Decision(
            result,
            {
                key: {
                    "request": fingerprint,
                    "result": json.dumps(result),
                    "participants": json.dumps([offer.user_id for offer in offers]),
                }
            },
        )

    await require_durable(redis)
    result = await transact(
        redis,
        (Resource(key, "hash"),),
        operation_id(),
        {"cancel": identity, "request": fingerprint},
        decide,
    )
    await require_durable(redis)
    return result
