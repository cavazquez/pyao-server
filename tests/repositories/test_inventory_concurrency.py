"""La inicialización y MOVE_ITEM comparten las garantías de las transacciones de recursos."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from src.command_handlers.move_item_handler import MoveItemCommandHandler
from src.commands.move_item_command import MoveItemCommand
from src.models.item_catalog import ItemCatalog
from src.repositories.bank_repository import BankRepository
from src.repositories.inventory_repository import InventoryRepository
from src.utils.inventory_storage import InventoryStorage
from src.utils.redis_config import RedisKeys


@pytest.mark.asyncio
@pytest.mark.parametrize("container", ["inventory", "bank"])
async def test_empty_initialization_cannot_erase_concurrent_credit(redis_client, container):
    """Un hash vacío leído antes de una entrega no autoriza sobrescribirla después."""
    entered, resume = asyncio.Event(), asyncio.Event()
    original = redis_client.hgetall
    key = RedisKeys.player_inventory(1) if container == "inventory" else RedisKeys.bank(1)
    first = True

    async def delayed_read(resource_key: str):
        nonlocal first
        result = await original(resource_key)
        if resource_key == key and first:
            first = False
            entered.set()
            await resume.wait()
        return result

    get_values = (
        InventoryStorage(redis_client).get_all_slots
        if container == "inventory"
        else BankRepository(redis_client).get_bank
    )
    with patch.object(redis_client, "hgetall", delayed_read):
        initializing = asyncio.create_task(get_values(1))
        await asyncio.wait_for(entered.wait(), 2)
        await redis_client.hset(key, mapping={"slot_30": "1:3"})
        resume.set()
        await initializing
    assert (await redis_client.hgetall(key))["slot_30"] == "1:3"


@pytest.mark.asyncio
async def test_move_keeps_equipment_stats_and_price_on_client_update(redis_client):
    """La actualización del slot 30 conserva equipo, precio y atributos de la espada."""
    inventory = InventoryRepository(redis_client)
    await inventory.set_slot(1, 1, 2, 1)
    await redis_client.hset(RedisKeys.player_equipment(1), mapping={"weapon": "1"})
    sender = AsyncMock()
    handler = MoveItemCommandHandler(inventory, ItemCatalog(), sender)
    assert (await handler.handle(MoveItemCommand(1, 1, 30))).success
    updates = [call.kwargs for call in sender.send_change_inventory_slot.await_args_list]
    target = next(update for update in updates if update["slot"] == 30)
    assert target["equipped"]
    assert target["sale_price"] == 210
    assert target["max_hit"] == 8
    assert target["min_hit"] == 1
    assert target["item_type"] == 2
