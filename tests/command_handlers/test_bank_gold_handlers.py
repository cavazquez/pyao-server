"""Tests para handlers de banco (depositar/extraer oro)."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.command_handlers.bank_deposit_gold_handler import BankDepositGoldCommandHandler
from src.command_handlers.bank_extract_gold_handler import BankExtractGoldCommandHandler
from src.commands.bank_deposit_gold_command import BankDepositGoldCommand
from src.commands.bank_extract_gold_command import BankExtractGoldCommand
from src.commands.walk_command import WalkCommand


@pytest.fixture
def mock_bank_repo() -> MagicMock:
    """Mock de BankRepository."""
    repo = MagicMock()
    repo.add_gold = AsyncMock(return_value=500)
    repo.get_gold = AsyncMock(return_value=500)
    repo.remove_gold = AsyncMock(return_value=True)
    return repo


@pytest.fixture
def mock_player_repo() -> MagicMock:
    """Mock de PlayerRepository."""
    repo = MagicMock()
    repo.get_gold = AsyncMock(return_value=1000)
    repo.remove_gold = AsyncMock(return_value=True)
    repo.add_gold = AsyncMock()
    return repo


@pytest.fixture
def mock_message_sender() -> MagicMock:
    """Mock de MessageSender."""
    sender = MagicMock()
    sender.send_console_msg = AsyncMock()
    sender.send_update_gold = AsyncMock()
    sender.send_update_bank_gold = AsyncMock()
    return sender


@pytest.mark.asyncio
async def test_deposit_gold_success(
    mock_bank_repo: MagicMock,
    mock_player_repo: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test depositar oro exitosamente."""
    handler = BankDepositGoldCommandHandler(
        bank_repo=mock_bank_repo,
        player_repo=mock_player_repo,
        message_sender=mock_message_sender,
    )

    command = BankDepositGoldCommand(user_id=1, amount=500)
    result = await handler.handle(command)

    assert result.success is True
    assert result.data["amount"] == 500


@pytest.mark.asyncio
async def test_deposit_gold_insufficient(
    mock_bank_repo: MagicMock,
    mock_player_repo: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test depositar oro insuficiente."""
    mock_player_repo.get_gold = AsyncMock(return_value=100)

    handler = BankDepositGoldCommandHandler(
        bank_repo=mock_bank_repo,
        player_repo=mock_player_repo,
        message_sender=mock_message_sender,
    )

    command = BankDepositGoldCommand(user_id=1, amount=500)
    result = await handler.handle(command)

    assert result.success is False
    assert "suficiente" in result.error_message.lower()


@pytest.mark.asyncio
async def test_deposit_gold_invalid_amount(
    mock_bank_repo: MagicMock,
    mock_player_repo: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test depositar oro con cantidad inválida."""
    handler = BankDepositGoldCommandHandler(
        bank_repo=mock_bank_repo,
        player_repo=mock_player_repo,
        message_sender=mock_message_sender,
    )

    command = BankDepositGoldCommand(user_id=1, amount=0)
    result = await handler.handle(command)

    assert result.success is False
    assert "mayor a 0" in result.error_message.lower()


@pytest.mark.asyncio
async def test_extract_gold_success(
    mock_bank_repo: MagicMock,
    mock_player_repo: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test extraer oro exitosamente."""
    handler = BankExtractGoldCommandHandler(
        bank_repo=mock_bank_repo,
        player_repo=mock_player_repo,
        message_sender=mock_message_sender,
    )

    command = BankExtractGoldCommand(user_id=1, amount=300)
    result = await handler.handle(command)

    assert result.success is True
    assert result.data["amount"] == 300


@pytest.mark.asyncio
async def test_extract_gold_insufficient(
    mock_bank_repo: MagicMock,
    mock_player_repo: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test extraer oro insuficiente en banco."""
    mock_bank_repo.get_gold = AsyncMock(return_value=100)

    handler = BankExtractGoldCommandHandler(
        bank_repo=mock_bank_repo,
        player_repo=mock_player_repo,
        message_sender=mock_message_sender,
    )

    command = BankExtractGoldCommand(user_id=1, amount=500)
    result = await handler.handle(command)

    assert result.success is False
    assert "suficiente" in result.error_message.lower()


@pytest.mark.asyncio
async def test_extract_gold_invalid_amount(
    mock_bank_repo: MagicMock,
    mock_player_repo: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test extraer oro con cantidad inválida."""
    handler = BankExtractGoldCommandHandler(
        bank_repo=mock_bank_repo,
        player_repo=mock_player_repo,
        message_sender=mock_message_sender,
    )

    command = BankExtractGoldCommand(user_id=1, amount=-10)
    result = await handler.handle(command)

    assert result.success is False
    assert "mayor a 0" in result.error_message.lower()


@pytest.mark.asyncio
async def test_deposit_invalid_command(
    mock_bank_repo: MagicMock,
    mock_player_repo: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test depositar con comando inválido."""
    handler = BankDepositGoldCommandHandler(
        bank_repo=mock_bank_repo,
        player_repo=mock_player_repo,
        message_sender=mock_message_sender,
    )

    invalid_command = WalkCommand(user_id=1, heading=2)
    result = await handler.handle(invalid_command)

    assert result.success is False


@pytest.mark.asyncio
async def test_extract_invalid_command(
    mock_bank_repo: MagicMock,
    mock_player_repo: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test extraer con comando inválido."""
    handler = BankExtractGoldCommandHandler(
        bank_repo=mock_bank_repo,
        player_repo=mock_player_repo,
        message_sender=mock_message_sender,
    )

    invalid_command = WalkCommand(user_id=1, heading=2)
    result = await handler.handle(invalid_command)

    assert result.success is False
