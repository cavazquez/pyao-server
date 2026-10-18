"""Drop identificado con débito y suelo conjuntos y notificación posterior."""

import pytest

from src.command_handlers.drop_handler import DropCommandHandler
from src.commands.drop_command import DropCommand
from src.commands.walk_command import WalkCommand


def handler(world):
    """Construye el handler con el índice persistido que usa el servidor."""
    _redis, player, inventory, _ground, manager, catalog, sender, broadcast = world
    return DropCommandHandler(player, inventory, manager, broadcast, sender, catalog)


@pytest.mark.asyncio
async def test_drop_slot_30_replay_and_notification_once(ground_world):
    """Reintentar el comando no retira otro stack ni repite ObjectCreate."""
    _redis, _player, inventory, ground, manager, _catalog, sender, broadcast = ground_world
    await inventory.set_slot(1, 30, 1, 5)
    command = DropCommand(1, 30, 3)
    drop = handler(ground_world)
    assert (await drop.handle(command)).success
    assert (await drop.handle(command)).success
    assert await inventory.get_slot(1, 30) == (1, 2)
    rows = (await ground.load_ground_items(1))[50, 50]
    assert len(rows) == 1
    assert rows[0]["quantity"] == 3
    assert rows[0]["stack_id"].startswith("g1.")
    assert manager.get_ground_items(1, 50, 50) == rows
    assert sender.send_change_inventory_slot.await_count == 30
    assert broadcast.broadcast_object_create.await_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("slot", [0, 31])
async def test_gold_slots_and_clamping_are_preserved(ground_world, slot):
    """Clásico y Godot retiran hasta el saldo disponible, sin moneda negativa."""
    _redis, player, _inventory, ground, _manager, _catalog, _sender, _broadcast = ground_world
    command = DropCommand(1, slot, 500)
    drop = handler(ground_world)
    assert (await drop.handle(command)).success
    assert (await drop.handle(command)).success
    assert await player.get_gold(1) == 0
    rows = (await ground.load_ground_items(1))[50, 50]
    assert len(rows) == 1
    assert rows[0]["item_id"] == 12
    assert rows[0]["quantity"] == 100


@pytest.mark.asyncio
async def test_full_tile_and_equipped_item_do_not_debit_inventory(ground_world):
    """Ni un tile completo ni equipo activo autorizan a retirar el objeto."""
    redis, _player, inventory, ground, _manager, _catalog, sender, _broadcast = ground_world
    await inventory.set_slot(1, 30, 1, 5)
    for _ in range(10):
        await ground.add_ground_item(1, 50, 50, {"item_id": 1, "quantity": 1})
    assert not (await handler(ground_world).handle(DropCommand(1, 30, 2))).success
    assert await inventory.get_slot(1, 30) == (1, 5)
    await ground.clear_ground_items(1)
    await redis.hset("player:1:equipment", mapping={"armor": "30"})
    assert not (await handler(ground_world).handle(DropCommand(1, 30, 2))).success
    assert await inventory.get_slot(1, 30) == (1, 5)
    sender.send_change_inventory_slot.assert_not_awaited()


@pytest.mark.asyncio
async def test_stale_slot_and_invalid_command_do_not_drop_another_item(ground_world):
    """Una identidad de origen cambiada no descarta el nuevo contenido del slot."""
    _redis, _player, inventory, ground, _manager, _catalog, _sender, _broadcast = ground_world
    await inventory.set_slot(1, 30, 2, 1)
    command = DropCommand(1, 30, 1, expected_item_id=1)
    assert not (await handler(ground_world).handle(command)).success
    assert await inventory.get_slot(1, 30) == (2, 1)
    assert await ground.load_ground_items(1) == {}
    assert not (await handler(ground_world).handle(DropCommand(1, 30, -1))).success
    assert not (await handler(ground_world).handle(WalkCommand(1, 1))).success
