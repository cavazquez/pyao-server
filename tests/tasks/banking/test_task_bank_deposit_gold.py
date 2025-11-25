"""Tests para TaskBankDepositGold."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.commands.bank_deposit_gold_command import BankDepositGoldCommand
from src.commands.base import CommandResult
from src.tasks.banking.task_bank_deposit_gold import TaskBankDepositGold


def create_mock_bank_deposit_gold_handler(
    bank_repo: MagicMock | None = None,
    player_repo: MagicMock | None = None,
    message_sender: MagicMock | None = None,
) -> MagicMock:
    """Crea un mock de BankDepositGoldCommandHandler con las dependencias especificadas."""
    handler = MagicMock()
    handler.bank_repo = bank_repo or MagicMock()
    handler.player_repo = player_repo or MagicMock()
    handler.message_sender = message_sender or MagicMock()
    handler.handle = AsyncMock()
    return handler


@pytest.mark.asyncio
class TestTaskBankDepositGold:
    """Tests para TaskBankDepositGold."""

    async def test_deposit_gold_success(self) -> None:
        """Test de depósito de oro exitoso."""
        # Setup
        message_sender = MagicMock()
        message_sender.connection.address = "127.0.0.1:1234"
        message_sender.send_console_msg = AsyncMock()
        message_sender.send_update_gold = AsyncMock()
        message_sender.send_update_bank_gold = AsyncMock()

        bank_deposit_gold_handler = create_mock_bank_deposit_gold_handler(
            message_sender=message_sender
        )
        bank_deposit_gold_handler.handle.return_value = CommandResult.ok(
            data={"amount": 100, "bank_gold": 100}
        )

        # Packet: BANK_DEPOSIT_GOLD + amount=100
        data = bytes([0x70, 0x64, 0x00, 0x00, 0x00])  # 112 + 100 en int32
        session_data = {"user_id": 1}

        task = TaskBankDepositGold(
            data,
            message_sender,
            amount=100,
            bank_deposit_gold_handler=bank_deposit_gold_handler,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert
        bank_deposit_gold_handler.handle.assert_called_once()
        call_args = bank_deposit_gold_handler.handle.call_args[0][0]
        assert isinstance(call_args, BankDepositGoldCommand)
        assert call_args.user_id == 1
        assert call_args.amount == 100

    async def test_deposit_gold_amount_zero(self) -> None:
        """Test de depósito con cantidad 0."""
        # Setup
        message_sender = MagicMock()
        message_sender.connection.address = "127.0.0.1:1234"
        message_sender.send_console_msg = AsyncMock()

        bank_deposit_gold_handler = create_mock_bank_deposit_gold_handler(
            message_sender=message_sender
        )
        bank_deposit_gold_handler.handle.return_value = CommandResult.error(
            "Cantidad inválida: debe ser mayor a 0"
        )

        data = bytes([0x70, 0x00, 0x00, 0x00, 0x00])
        session_data = {"user_id": 1}

        task = TaskBankDepositGold(
            data,
            message_sender,
            amount=0,
            bank_deposit_gold_handler=bank_deposit_gold_handler,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert
        bank_deposit_gold_handler.handle.assert_called_once()

    async def test_deposit_gold_insufficient_funds(self) -> None:
        """Test de depósito sin suficiente oro en inventario."""
        # Setup
        message_sender = MagicMock()
        message_sender.connection.address = "127.0.0.1:1234"
        message_sender.send_console_msg = AsyncMock()

        bank_deposit_gold_handler = create_mock_bank_deposit_gold_handler(
            message_sender=message_sender
        )
        bank_deposit_gold_handler.handle.return_value = CommandResult.error(
            "No tienes suficiente oro. Tienes: 50"
        )

        data = bytes([0x70, 0x64, 0x00, 0x00, 0x00])
        session_data = {"user_id": 1}

        task = TaskBankDepositGold(
            data,
            message_sender,
            amount=100,  # Intenta depositar 100
            bank_deposit_gold_handler=bank_deposit_gold_handler,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert
        bank_deposit_gold_handler.handle.assert_called_once()

    async def test_deposit_gold_without_session(self) -> None:
        """Test sin sesión activa."""
        # Setup
        message_sender = MagicMock()
        bank_deposit_gold_handler = create_mock_bank_deposit_gold_handler(
            message_sender=message_sender
        )

        data = bytes([0x70, 0x64, 0x00, 0x00, 0x00])
        session_data = {}  # Sin user_id

        task = TaskBankDepositGold(
            data,
            message_sender,
            amount=100,
            bank_deposit_gold_handler=bank_deposit_gold_handler,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert - no debe llamar al handler
        bank_deposit_gold_handler.handle.assert_not_called()

    async def test_deposit_gold_without_handler(self) -> None:
        """Test sin handler."""
        # Setup
        message_sender = MagicMock()
        message_sender.connection.address = "127.0.0.1:1234"
        message_sender.send_console_msg = AsyncMock()

        data = bytes([0x70, 0x64, 0x00, 0x00, 0x00])
        session_data = {"user_id": 1}

        task = TaskBankDepositGold(
            data,
            message_sender,
            amount=100,
            bank_deposit_gold_handler=None,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert
        message_sender.send_console_msg.assert_called_once()
        assert "Error" in message_sender.send_console_msg.call_args[0][0]
