"""Apilamiento con Redis concreto: totalidad, concurrencia y conservación de cantidades."""

import asyncio

import pytest

from src.repositories.inventory_repository import InventoryRepository
from src.utils.redis_config import RedisKeys


@pytest.mark.asyncio
async def test_stack_distribution_and_conditional_remove(redis_client):
    """Se distribuyen cantidades completas y no se retira parcialmente si no alcanza."""
    repo = InventoryRepository(redis_client)
    assert await repo.add_item(1, 10, 45) == [(1, 20), (2, 20), (3, 5)]
    assert await repo.remove_item(1, 1, 21) is False
    assert await repo.get_slot(1, 1) == (10, 20)
    assert await repo.remove_item(1, 1, 20) is True
    assert await repo.get_slot(1, 1) is None
    assert await repo.remove_item_by_item_id(1, 10, 26) is False
    assert await repo.get_slot(1, 2) == (10, 20)
    assert await repo.remove_item_by_item_id(1, 10, 25) is True
    assert await repo.get_inventory_slots(1) == {}


@pytest.mark.asyncio
async def test_partial_capacity_does_not_write_initial_stacks(redis_client):
    """La última unidad que no entra cancela la distribución completa."""
    repo = InventoryRepository(redis_client)
    for slot in range(1, 31):
        await repo.set_slot(1, slot, 10, 20)
    await repo.set_slot(1, 30, 10, 19)
    assert await repo.add_item(1, 10, 2) == []
    assert await repo.get_slot(1, 30) == (10, 19)
    assert await repo.add_item(1, 10, 1) == [(30, 20)]
    for invalid in [0, -1, True, 1.5, "1"]:
        assert await repo.add_item(1, 10, invalid) == []
    assert await repo.remove_item(1, 1, -1) is False


@pytest.mark.asyncio
async def test_concurrent_gains_and_debits_preserve_total(redis_client):
    """Los incrementos por trabajo y consumo compiten sobre el mismo hash sin pisarse."""
    repo = InventoryRepository(redis_client)
    await asyncio.gather(*(repo.add_item(1, 10, 1) for _ in range(30)))
    assert sum(slot.quantity for slot in (await repo.get_inventory_slots(1)).values()) == 30
    results = await asyncio.gather(*(repo.remove_item_by_item_id(1, 10, 20) for _ in range(2)))
    assert sum(results) == 1
    assert sum(slot.quantity for slot in (await repo.get_inventory_slots(1)).values()) == 10


@pytest.mark.asyncio
async def test_swap_moves_equipment_reference_atomically(redis_client):
    """Arrastrar un objeto equipado conserva el objeto y la referencia en el mismo commit."""
    repo = InventoryRepository(redis_client)
    await repo.set_slot(1, 1, 2, 1)
    await redis_client.hset(RedisKeys.player_equipment(1), mapping={"weapon": "1"})
    result = await repo.swap_slots(1, 1, 30)
    assert result.success
    assert result.old_slot_data is None
    assert result.new_slot_data == (2, 1)
    assert result.new_equipped
    assert (await redis_client.hgetall(RedisKeys.player_equipment(1)))["weapon"] == "30"
    assert await repo.remove_item(1, 30, 1) is False
