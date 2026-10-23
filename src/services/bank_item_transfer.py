"""Transferencia completa de stacks entre inventario y banco, con recibo y AOF."""

from typing import TYPE_CHECKING, Any, Literal, cast

from src.models.items_catalog import ITEMS_CATALOG
from src.utils.durability import require_durable
from src.utils.redis_config import RedisKeys
from src.utils.resource_transaction import Decision, Resource, Snapshot, transact
from src.utils.slot_plan import SlotPlan

if TYPE_CHECKING:
    from redis.asyncio import Redis

MAX_BANK_STACK = 32767


async def transfer_bank_item(
    redis: Redis,
    user_id: int,
    slot: int,
    quantity: int,
    direction: Literal["deposit", "withdraw"],
    identity: str,
    *,
    inventory_slots: int = 30,
    bank_slots: int = 40,
    inventory_stack: int = 20,
) -> dict[str, Any]:
    """Confirma origen, destino y recibo antes de actualizar las ventanas.

    Returns:
        Resultado confirmado; un rechazo deja ambos contenedores sin modificaciones.

    Raises:
        ValueError: Ante cantidad, slot, usuario o dirección inválidos.
    """
    source_capacity = inventory_slots if direction == "deposit" else bank_slots
    if type(quantity) is not int or not 1 <= quantity <= MAX_BANK_STACK:
        msg = "Cantidad de objetos inválida"
        raise ValueError(msg)
    if user_id < 1 or not 1 <= slot <= source_capacity or direction not in {"deposit", "withdraw"}:
        msg = "Slot o transferencia inválidos"
        raise ValueError(msg)
    inventory_key, bank_key = RedisKeys.player_inventory(user_id), RedisKeys.bank(user_id)
    equipment_key = RedisKeys.player_equipment(user_id)
    first_item_id: int | None = None

    def decide(snapshot: Snapshot) -> Decision:
        nonlocal first_item_id
        try:
            inventory_before = cast("dict[str, str]", snapshot[inventory_key])
            bank_before = cast("dict[str, str]", snapshot[bank_key])
            inventory = SlotPlan(inventory_before, inventory_slots, inventory_stack)
            bank = SlotPlan(bank_before, bank_slots, MAX_BANK_STACK)
            source, destination = (inventory, bank) if direction == "deposit" else (bank, inventory)
            item = source.slots.get(slot)
            if item is None:
                return Decision({"applied": False, "error": "No hay ningún objeto en ese slot"}, {})
            if first_item_id is None:
                first_item_id = item.item_id
            if item.item_id != first_item_id:
                return Decision(
                    {"applied": False, "error": "El objeto del slot cambió; seleccioná nuevamente"},
                    {},
                )
            definition = ITEMS_CATALOG.get(item.item_id)
            if definition is None:
                return Decision({"applied": False, "error": "Objeto no encontrado en catálogo"}, {})
            if (
                direction == "deposit"
                and str(slot) in cast("dict[str, str]", snapshot[equipment_key]).values()
            ):
                return Decision(
                    {"applied": False, "error": "Desequipá el objeto antes de depositarlo"}, {}
                )
            removed = source.take(slot, item.item_id, quantity)
            destination.give(item.item_id, quantity, instance_ids=removed.instance_ids)
            inventory_after, bank_after = inventory.fields(), bank.fields()
            inventory_changed = [
                int(key.removeprefix("slot_"))
                for key, value in inventory_after.items()
                if inventory_before.get(key, "") != value
            ]
            bank_changed = [
                int(key.removeprefix("slot_"))
                for key, value in bank_after.items()
                if bank_before.get(key, "") != value
            ]
            result = {
                "applied": True,
                "item_id": item.item_id,
                "quantity": quantity,
                "name": definition.name,
                "inventory_slots": inventory_changed,
                "bank_slots": bank_changed,
                "bank_slot": bank_changed[0],
            }
            return Decision(result, {inventory_key: inventory_after, bank_key: bank_after})
        except ValueError as error:
            return Decision({"applied": False, "error": str(error)}, {})

    await require_durable(redis)
    result = await transact(
        redis,
        (
            Resource(inventory_key, "hash"),
            Resource(bank_key, "hash"),
            Resource(equipment_key, "hash"),
        ),
        identity,
        {
            "user_id": user_id,
            "slot": slot,
            "quantity": quantity,
            "direction": direction,
            "inventory_slots": inventory_slots,
            "bank_slots": bank_slots,
            "inventory_stack": inventory_stack,
        },
        decide,
    )
    await require_durable(redis)
    return result
