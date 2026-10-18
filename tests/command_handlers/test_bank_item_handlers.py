"""Banco e inventario concretos: transferencias completas y avisos postcommit."""

from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio

from src.command_handlers.bank_deposit_handler import BankDepositCommandHandler
from src.command_handlers.bank_extract_handler import BankExtractCommandHandler
from src.commands.bank_deposit_command import BankDepositCommand
from src.commands.bank_extract_command import BankExtractCommand
from src.commands.walk_command import WalkCommand
from src.repositories.bank_repository import BankRepository
from src.repositories.inventory_repository import InventoryRepository
from src.repositories.player_repository import PlayerRepository
from src.utils.redis_config import RedisKeys


@pytest_asyncio.fixture
async def bank_setup(redis_client):
    """Comparte contenedores persistidos; sustituye sólo fsync de Redis fake.

    Yields:
        Cliente Redis, banco, inventario, jugador y emisor.
    """
    bank, inventory = BankRepository(redis_client), InventoryRepository(redis_client)
    sender = AsyncMock()
    await inventory.set_slot(1, 30, 1, 45)
    with patch("src.services.bank_item_transfer.require_durable", new=AsyncMock()):
        yield redis_client, bank, inventory, PlayerRepository(redis_client), sender


@pytest.mark.asyncio
async def test_round_trip_distributes_stacks_and_replays_once(bank_setup):
    """El slot 30 y una bóveda casi al tope distribuyen sin perder el remanente."""
    redis, bank, inventory, player, sender = bank_setup
    await redis.hset(RedisKeys.bank(1), mapping={"slot_1": "1:32760"})
    deposit = BankDepositCommandHandler(bank, inventory, player, sender)
    command = BankDepositCommand(1, 30, 42)
    assert (await deposit.handle(command)).success
    assert (await deposit.handle(command)).success
    assert await inventory.get_slot(1, 30) == (1, 3)
    assert (await bank.get_item(1, 1)).quantity == 32767
    assert (await bank.get_item(1, 2)).quantity == 35
    extract = BankExtractCommandHandler(bank, inventory, player, sender)
    command = BankExtractCommand(1, 2, 27)
    assert (await extract.handle(command)).success
    assert (await extract.handle(command)).success
    assert await inventory.get_slot(1, 30) == (1, 20)
    assert await inventory.get_slot(1, 1) == (1, 10)
    assert (await bank.get_item(1, 2)).quantity == 8
    # Cada confirmación sincroniza también slots vacíos, sin optimismo local.
    assert sender.send_change_inventory_slot.await_count == 120
    assert sender.send_change_bank_slot.await_count == 160
    reconnected = InventoryRepository(redis)
    assert await reconnected.get_slot(1, 30) == (1, 20)


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["bank_full", "partial_stack", "inventory_full", "equipped"])
async def test_rejected_transfer_preserves_both_containers(bank_setup, kind):
    """Capacidad parcial insuficiente tampoco persiste los primeros stacks calculados."""
    redis, bank, inventory, player, sender = bank_setup
    if kind in {"bank_full", "partial_stack"}:
        await redis.hset(RedisKeys.bank(1), mapping={f"slot_{i}": "2:32767" for i in range(1, 41)})
        if kind == "partial_stack":
            await redis.hset(RedisKeys.bank(1), mapping={"slot_1": "1:32760"})
        handler, command = BankDepositCommandHandler, BankDepositCommand(1, 30, 10)
    elif kind == "inventory_full":
        for slot in range(1, 31):
            await inventory.set_slot(1, slot, 2, 20)
        await redis.hset(RedisKeys.bank(1), mapping={"slot_1": "1:10"})
        handler, command = BankExtractCommandHandler, BankExtractCommand(1, 1, 10)
    else:
        await redis.hset(RedisKeys.player_equipment(1), mapping={"weapon": "30"})
        handler, command = BankDepositCommandHandler, BankDepositCommand(1, 30, 10)
    before = (
        await redis.hgetall(RedisKeys.player_inventory(1)),
        await redis.hgetall(RedisKeys.bank(1)),
    )
    assert not (await handler(bank, inventory, player, sender).handle(command)).success
    assert (
        await redis.hgetall(RedisKeys.player_inventory(1)),
        await redis.hgetall(RedisKeys.bank(1)),
    ) == before
    sender.send_change_inventory_slot.assert_not_awaited()
    sender.send_change_bank_slot.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("handler", [BankDepositCommandHandler, BankExtractCommandHandler])
async def test_invalid_command_is_not_a_transfer(bank_setup, handler):
    """El handler no muta ni notifica inventarios para otro tipo de comando."""
    _redis, bank, inventory, player, sender = bank_setup
    assert not (await handler(bank, inventory, player, sender).handle(WalkCommand(1, 1))).success
    sender.send_change_inventory_slot.assert_not_awaited()
