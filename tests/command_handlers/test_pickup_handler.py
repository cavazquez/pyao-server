"""Pickup persistido: identidad estable, competencia, remanente y replay confirmado."""

import asyncio

import pytest

from src.command_handlers.pickup_handler import PickupCommandHandler
from src.commands.pickup_command import PickupCommand
from src.commands.walk_command import WalkCommand
from src.models.item_constants import MAX_PLAYER_GOLD


def handler(world):
    """Construye el handler con repositorios concretos y sólo emisores sustituidos."""
    _redis, player, inventory, _ground, manager, catalog, sender, broadcast = world
    return PickupCommandHandler(player, inventory, manager, broadcast, catalog, None, sender)


@pytest.mark.asyncio
async def test_pickup_commits_ground_and_inventory_then_replays_once(ground_world):
    """El mismo comando no acredita ni publica dos veces un stack."""
    _redis, _player, inventory, ground, manager, _catalog, sender, broadcast = ground_world
    await ground.add_ground_item(1, 50, 50, {"item_id": 1, "quantity": 25, "grh_index": 1})
    command = PickupCommand(1)
    pickup = handler(ground_world)
    assert (await pickup.handle(command)).success
    assert (await pickup.handle(command)).success
    assert sum(item.quantity for item in (await inventory.get_inventory_slots(1)).values()) == 25
    assert await ground.load_ground_items(1) == {}
    assert manager.get_ground_items(1, 50, 50) == []
    assert sender.send_change_inventory_slot.await_count == 30
    assert broadcast.broadcast_object_delete.await_count == 1


@pytest.mark.asyncio
async def test_two_players_cannot_credit_the_same_identified_stack(ground_world):
    """Ambos ven la misma identidad; uno solo la consume, sin claim local ni compensación."""
    _redis, _player, inventory, ground, _manager, _catalog, _sender, _broadcast = ground_world
    result = await ground.add_ground_item(1, 50, 50, {"item_id": 1, "quantity": 5})
    identity = result["item"]["stack_id"]
    commands = [
        PickupCommand(user_id, expected_stack_id=identity, expected_item_id=1, origin=(1, 50, 50))
        for user_id in [1, 2]
    ]
    pickup = handler(ground_world)
    results = await asyncio.gather(*(pickup.handle(command) for command in commands))
    assert sum(result.success for result in results) == 1
    inventories = await asyncio.gather(
        *(inventory.get_inventory_slots(user_id) for user_id in [1, 2])
    )
    assert sum(item.quantity for values in inventories for item in values.values()) == 5


@pytest.mark.asyncio
async def test_partial_gold_keeps_same_identified_remainder(ground_world):
    """El tope acepta sólo cien monedas y conserva cuatrocientas del mismo stack."""
    _redis, player, _inventory, ground, _manager, _catalog, _sender, _broadcast = ground_world
    await player.update_gold(1, MAX_PLAYER_GOLD - 100)
    spawned = await ground.add_ground_item(1, 50, 50, {"item_id": 12, "quantity": 500})
    assert (await handler(ground_world).handle(PickupCommand(1))).success
    assert await player.get_gold(1) == MAX_PLAYER_GOLD
    remaining = (await ground.load_ground_items(1))[50, 50][0]
    assert remaining["quantity"] == 400
    assert remaining["stack_id"] == spawned["item"]["stack_id"]
    assert not (await handler(ground_world).handle(PickupCommand(1))).success
    assert (await ground.load_ground_items(1))[50, 50][0]["quantity"] == 400


@pytest.mark.asyncio
async def test_full_inventory_keeps_complete_ground_stack(ground_world):
    """La capacidad parcial del destino no consume parte del suelo."""
    _redis, _player, inventory, ground, _manager, _catalog, sender, _broadcast = ground_world
    for slot in range(1, 31):
        await inventory.set_slot(1, slot, 1, 20)
    await inventory.set_slot(1, 30, 1, 19)
    await ground.add_ground_item(1, 50, 50, {"item_id": 1, "quantity": 2})
    assert not (await handler(ground_world).handle(PickupCommand(1))).success
    assert await inventory.get_slot(1, 30) == (1, 19)
    assert (await ground.load_ground_items(1))[50, 50][0]["quantity"] == 2
    sender.send_change_inventory_slot.assert_not_awaited()


@pytest.mark.asyncio
async def test_invalid_or_empty_pickup_does_not_create_resources(ground_world):
    """El mapa vacío y otro tipo de comando no acreditan recursos."""
    assert not (await handler(ground_world).handle(PickupCommand(1))).success
    assert not (await handler(ground_world).handle(WalkCommand(1, 1))).success
