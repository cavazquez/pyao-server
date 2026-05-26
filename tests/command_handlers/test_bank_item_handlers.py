"""Tests para handlers de banco (depositar/extraer items)."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.command_handlers.bank_deposit_handler import BankDepositCommandHandler
from src.command_handlers.bank_extract_handler import BankExtractCommandHandler
from src.commands.bank_deposit_command import BankDepositCommand
from src.commands.bank_extract_command import BankExtractCommand
from src.commands.walk_command import WalkCommand
from src.repositories.bank_repository import BankItem


@pytest.fixture
def mock_bank_repo() -> MagicMock:
    """Mock de BankRepository."""
    repo = MagicMock()
    repo.deposit_item = AsyncMock(return_value=3)
    repo.extract_item = AsyncMock(return_value=True)
    repo.get_item = AsyncMock(
        return_value=BankItem(slot=3, item_id=1, quantity=5),
    )
    return repo


@pytest.fixture
def mock_inventory_repo() -> MagicMock:
    """Mock de InventoryRepository."""
    repo = MagicMock()
    repo.get_slot = AsyncMock(return_value=(1, 10))
    repo.remove_item = AsyncMock(return_value=True)
    repo.add_item = AsyncMock(return_value=[(2, 5)])
    return repo


@pytest.fixture
def mock_player_repo() -> MagicMock:
    """Mock de PlayerRepository."""
    return MagicMock()


@pytest.fixture
def mock_message_sender() -> MagicMock:
    """Mock de MessageSender."""
    sender = MagicMock()
    sender.send_console_msg = AsyncMock()
    sender.send_change_inventory_slot = AsyncMock()
    sender.send_change_bank_slot = AsyncMock()
    return sender


@pytest.mark.asyncio
async def test_deposit_item_success(
    mock_bank_repo: MagicMock,
    mock_inventory_repo: MagicMock,
    mock_player_repo: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Depositar item exitosamente."""
    handler = BankDepositCommandHandler(
        bank_repo=mock_bank_repo,
        inventory_repo=mock_inventory_repo,
        player_repo=mock_player_repo,
        message_sender=mock_message_sender,
    )

    result = await handler.handle(BankDepositCommand(user_id=1, slot=5, quantity=5))

    assert result.success is True
    assert result.data == {"item_id": 1, "quantity": 5, "bank_slot": 3}
    mock_inventory_repo.remove_item.assert_awaited_once_with(1, 5, 5)


@pytest.mark.asyncio
async def test_deposit_item_empty_slot(
    mock_bank_repo: MagicMock,
    mock_inventory_repo: MagicMock,
    mock_player_repo: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Depositar desde slot vacío."""
    mock_inventory_repo.get_slot = AsyncMock(return_value=None)

    handler = BankDepositCommandHandler(
        bank_repo=mock_bank_repo,
        inventory_repo=mock_inventory_repo,
        player_repo=mock_player_repo,
        message_sender=mock_message_sender,
    )

    result = await handler.handle(BankDepositCommand(user_id=1, slot=5, quantity=1))

    assert result.success is False
    mock_bank_repo.deposit_item.assert_not_called()


@pytest.mark.asyncio
async def test_deposit_item_insufficient_quantity(
    mock_bank_repo: MagicMock,
    mock_inventory_repo: MagicMock,
    mock_player_repo: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Depositar más items de los que hay en el slot."""
    handler = BankDepositCommandHandler(
        bank_repo=mock_bank_repo,
        inventory_repo=mock_inventory_repo,
        player_repo=mock_player_repo,
        message_sender=mock_message_sender,
    )

    result = await handler.handle(BankDepositCommand(user_id=1, slot=5, quantity=20))

    assert result.success is False
    assert "solo tienes" in result.error_message.lower()


@pytest.mark.asyncio
async def test_deposit_item_bank_full(
    mock_bank_repo: MagicMock,
    mock_inventory_repo: MagicMock,
    mock_player_repo: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Depositar cuando el banco no tiene espacio."""
    mock_bank_repo.deposit_item = AsyncMock(return_value=None)

    handler = BankDepositCommandHandler(
        bank_repo=mock_bank_repo,
        inventory_repo=mock_inventory_repo,
        player_repo=mock_player_repo,
        message_sender=mock_message_sender,
    )

    result = await handler.handle(BankDepositCommand(user_id=1, slot=5, quantity=5))

    assert result.success is False
    mock_inventory_repo.remove_item.assert_not_called()


@pytest.mark.asyncio
async def test_deposit_item_remove_fails_rollback(
    mock_bank_repo: MagicMock,
    mock_inventory_repo: MagicMock,
    mock_player_repo: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Rollback si falla la remoción del inventario."""
    mock_inventory_repo.remove_item = AsyncMock(return_value=False)

    handler = BankDepositCommandHandler(
        bank_repo=mock_bank_repo,
        inventory_repo=mock_inventory_repo,
        player_repo=mock_player_repo,
        message_sender=mock_message_sender,
    )

    result = await handler.handle(BankDepositCommand(user_id=1, slot=5, quantity=5))

    assert result.success is False
    mock_bank_repo.extract_item.assert_awaited_once_with(1, 3, 5)


@pytest.mark.asyncio
async def test_deposit_invalid_command(
    mock_bank_repo: MagicMock,
    mock_inventory_repo: MagicMock,
    mock_player_repo: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Comando inválido en deposit handler."""
    handler = BankDepositCommandHandler(
        bank_repo=mock_bank_repo,
        inventory_repo=mock_inventory_repo,
        player_repo=mock_player_repo,
        message_sender=mock_message_sender,
    )

    result = await handler.handle(WalkCommand(user_id=1, heading=2))

    assert result.success is False


@pytest.mark.asyncio
async def test_extract_item_success(
    mock_bank_repo: MagicMock,
    mock_inventory_repo: MagicMock,
    mock_player_repo: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Extraer item exitosamente."""
    mock_bank_repo.get_item = AsyncMock(
        side_effect=[
            BankItem(slot=4, item_id=1, quantity=10),
            BankItem(slot=4, item_id=1, quantity=5),
        ]
    )

    handler = BankExtractCommandHandler(
        bank_repo=mock_bank_repo,
        inventory_repo=mock_inventory_repo,
        player_repo=mock_player_repo,
        message_sender=mock_message_sender,
    )

    result = await handler.handle(BankExtractCommand(user_id=1, slot=4, quantity=5))

    assert result.success is True
    assert result.data["item_id"] == 1
    mock_inventory_repo.add_item.assert_awaited_once_with(1, 1, 5)


@pytest.mark.asyncio
async def test_extract_item_empty_slot(
    mock_bank_repo: MagicMock,
    mock_inventory_repo: MagicMock,
    mock_player_repo: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Extraer de slot vacío del banco."""
    mock_bank_repo.get_item = AsyncMock(return_value=None)

    handler = BankExtractCommandHandler(
        bank_repo=mock_bank_repo,
        inventory_repo=mock_inventory_repo,
        player_repo=mock_player_repo,
        message_sender=mock_message_sender,
    )

    result = await handler.handle(BankExtractCommand(user_id=1, slot=4, quantity=1))

    assert result.success is False


@pytest.mark.asyncio
async def test_extract_item_inventory_full(
    mock_bank_repo: MagicMock,
    mock_inventory_repo: MagicMock,
    mock_player_repo: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Revertir extracción si el inventario está lleno."""
    mock_bank_repo.get_item = AsyncMock(return_value=BankItem(slot=4, item_id=1, quantity=10))
    mock_inventory_repo.add_item = AsyncMock(return_value=[])

    handler = BankExtractCommandHandler(
        bank_repo=mock_bank_repo,
        inventory_repo=mock_inventory_repo,
        player_repo=mock_player_repo,
        message_sender=mock_message_sender,
    )

    result = await handler.handle(BankExtractCommand(user_id=1, slot=4, quantity=5))

    assert result.success is False
    mock_bank_repo.deposit_item.assert_awaited_once_with(1, 1, 5)


@pytest.mark.asyncio
async def test_extract_invalid_command(
    mock_bank_repo: MagicMock,
    mock_inventory_repo: MagicMock,
    mock_player_repo: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Comando inválido en extract handler."""
    handler = BankExtractCommandHandler(
        bank_repo=mock_bank_repo,
        inventory_repo=mock_inventory_repo,
        player_repo=mock_player_repo,
        message_sender=mock_message_sender,
    )

    result = await handler.handle(WalkCommand(user_id=1, heading=2))

    assert result.success is False
