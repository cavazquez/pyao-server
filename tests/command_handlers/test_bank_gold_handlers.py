"""Banco con repositorios concretos: ambos saldos o ninguno y avisos confirmados."""

from unittest.mock import AsyncMock

import pytest

from src.command_handlers.bank_deposit_gold_handler import BankDepositGoldCommandHandler
from src.command_handlers.bank_extract_gold_handler import BankExtractGoldCommandHandler
from src.commands.bank_deposit_gold_command import BankDepositGoldCommand
from src.commands.bank_extract_gold_command import BankExtractGoldCommand
from src.commands.walk_command import WalkCommand
from src.repositories.bank_repository import BankRepository
from src.repositories.player_repository import PlayerRepository
from src.utils.redis_config import RedisKeys


@pytest.mark.asyncio
@pytest.mark.parametrize("withdraw", [False, True])
@pytest.mark.parametrize(("amount", "success"), [(40, True), (500, False), (0, False), (-1, False)])
async def test_transfer_commits_both_balances_and_replays_once(
    redis_client, withdraw, amount, success
):
    """El handler confirma dos saldos y una sola operación, incluso al repetir el comando."""
    player = PlayerRepository(redis_client)
    bank = BankRepository(redis_client)
    sender = AsyncMock()
    await player.update_gold(1, 100)
    await redis_client.set(RedisKeys.bank_gold(1), "100")
    command_type = BankExtractGoldCommand if withdraw else BankDepositGoldCommand
    handler_type = BankExtractGoldCommandHandler if withdraw else BankDepositGoldCommandHandler
    handler = handler_type(bank, player, sender)
    command = command_type(user_id=1, amount=amount)
    for _ in range(2):
        result = await handler.handle(command)
        assert result.success == success
    delta = (amount if withdraw else -amount) if success else 0
    assert await player.get_gold(1) == 100 + delta
    assert await bank.get_gold(1) == 100 - delta
    if success:
        sender.send_update_gold.assert_awaited_with(100 + delta)
        sender.send_update_bank_gold.assert_awaited_with(100 - delta)
    else:
        sender.send_update_gold.assert_not_awaited()
        sender.send_update_bank_gold.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "handler_type", [BankExtractGoldCommandHandler, BankDepositGoldCommandHandler]
)
async def test_bank_rejects_other_command(redis_client, handler_type):
    """Un comando de otro tipo no toca saldos ni anuncia éxito."""
    handler = handler_type(
        BankRepository(redis_client), PlayerRepository(redis_client), AsyncMock()
    )
    result = await handler.handle(WalkCommand(user_id=1, heading=1))
    assert not result.success
