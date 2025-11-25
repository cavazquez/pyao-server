"""Tests para TaskBankDeposit."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.commands.bank_deposit_command import BankDepositCommand
from src.commands.base import CommandResult
from src.tasks.banking.task_bank_deposit import TaskBankDeposit


def create_mock_bank_deposit_handler(
    bank_repo: MagicMock | None = None,
    inventory_repo: MagicMock | None = None,
    player_repo: MagicMock | None = None,
    message_sender: MagicMock | None = None,
) -> MagicMock:
    """Crea un mock de BankDepositCommandHandler con las dependencias especificadas."""
    handler = MagicMock()
    handler.bank_repo = bank_repo or MagicMock()
    handler.inventory_repo = inventory_repo or MagicMock()
    handler.player_repo = player_repo or MagicMock()
    handler.message_sender = message_sender or MagicMock()
    handler.handle = AsyncMock()
    return handler


@pytest.mark.asyncio
class TestTaskBankDeposit:
    """Tests para TaskBankDeposit."""

    async def test_deposit_success(self) -> None:
        """Test de depósito exitoso."""
        # Setup
        message_sender = MagicMock()
        message_sender.send_console_msg = AsyncMock()
        message_sender.send_change_inventory_slot = AsyncMock()
        message_sender.send_change_bank_slot = AsyncMock()

        bank_deposit_handler = create_mock_bank_deposit_handler(message_sender=message_sender)
        bank_deposit_handler.handle.return_value = CommandResult.ok(
            data={"item_id": 10, "quantity": 5, "bank_slot": 1}
        )

        # Packet: BANK_DEPOSIT + slot=3 + quantity=5
        data = bytes([43, 3, 5, 0])  # quantity en little-endian
        session_data = {"user_id": 1}

        task = TaskBankDeposit(
            data,
            message_sender,
            bank_deposit_handler=bank_deposit_handler,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert
        bank_deposit_handler.handle.assert_called_once()
        call_args = bank_deposit_handler.handle.call_args[0][0]
        assert isinstance(call_args, BankDepositCommand)
        assert call_args.user_id == 1
        assert call_args.slot == 3
        assert call_args.quantity == 5

    async def test_deposit_without_session(self) -> None:
        """Test de depósito sin sesión activa."""
        # Setup
        message_sender = MagicMock()
        bank_deposit_handler = create_mock_bank_deposit_handler(message_sender=message_sender)

        data = bytes([43, 1, 1, 0])
        session_data = {}  # Sin user_id

        task = TaskBankDeposit(
            data,
            message_sender,
            bank_deposit_handler=bank_deposit_handler,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert - no debe hacer nada
        bank_deposit_handler.handle.assert_not_called()

    async def test_deposit_invalid_quantity(self) -> None:
        """Test de depósito con cantidad inválida."""
        # Setup
        message_sender = MagicMock()
        message_sender.send_console_msg = AsyncMock()
        bank_deposit_handler = create_mock_bank_deposit_handler(message_sender=message_sender)

        # Packet con cantidad 0
        data = bytes([43, 1, 0, 0])
        session_data = {"user_id": 1}

        task = TaskBankDeposit(
            data,
            message_sender,
            bank_deposit_handler=bank_deposit_handler,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert - El validador da un mensaje más descriptivo
        message_sender.send_console_msg.assert_called_once()
        call_args = message_sender.send_console_msg.call_args[0][0]
        assert "Cantidad inválida" in call_args
        bank_deposit_handler.handle.assert_not_called()

    async def test_deposit_empty_slot(self) -> None:
        """Test de depósito desde slot vacío."""
        # Setup
        message_sender = MagicMock()
        message_sender.send_console_msg = AsyncMock()

        bank_deposit_handler = create_mock_bank_deposit_handler(message_sender=message_sender)
        bank_deposit_handler.handle.return_value = CommandResult.error(
            "No tienes ningún item en ese slot"
        )

        data = bytes([43, 1, 5, 0])
        session_data = {"user_id": 1}

        task = TaskBankDeposit(
            data,
            message_sender,
            bank_deposit_handler=bank_deposit_handler,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert
        bank_deposit_handler.handle.assert_called_once()

    async def test_deposit_insufficient_quantity(self) -> None:
        """Test de depósito con cantidad insuficiente."""
        # Setup
        message_sender = MagicMock()
        message_sender.send_console_msg = AsyncMock()

        bank_deposit_handler = create_mock_bank_deposit_handler(message_sender=message_sender)
        bank_deposit_handler.handle.return_value = CommandResult.error(
            "Solo tienes 3 items en ese slot"
        )

        # Intentar depositar 5 items
        data = bytes([43, 1, 5, 0])
        session_data = {"user_id": 1}

        task = TaskBankDeposit(
            data,
            message_sender,
            bank_deposit_handler=bank_deposit_handler,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert
        bank_deposit_handler.handle.assert_called_once()

    async def test_deposit_bank_full(self) -> None:
        """Test de depósito cuando el banco está lleno."""
        # Setup
        message_sender = MagicMock()
        message_sender.send_console_msg = AsyncMock()

        bank_deposit_handler = create_mock_bank_deposit_handler(message_sender=message_sender)
        bank_deposit_handler.handle.return_value = CommandResult.error(
            "No tienes espacio en el banco"
        )

        data = bytes([43, 1, 5, 0])
        session_data = {"user_id": 1}

        task = TaskBankDeposit(
            data,
            message_sender,
            bank_deposit_handler=bank_deposit_handler,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert
        bank_deposit_handler.handle.assert_called_once()

    async def test_deposit_remove_fails(self) -> None:
        """Test cuando falla la remoción del inventario.

        Verifica que se hace rollback del depósito en el banco.
        """
        # Setup
        message_sender = MagicMock()
        message_sender.send_console_msg = AsyncMock()

        bank_deposit_handler = create_mock_bank_deposit_handler(message_sender=message_sender)
        bank_deposit_handler.handle.return_value = CommandResult.error("Error al depositar")

        data = bytes([43, 1, 5, 0])
        session_data = {"user_id": 1}

        task = TaskBankDeposit(
            data,
            message_sender,
            bank_deposit_handler=bank_deposit_handler,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert - Debe hacer rollback (la lógica está en el handler)
        bank_deposit_handler.handle.assert_called_once()

    async def test_deposit_invalid_packet_size(self) -> None:
        """Test con packet de tamaño inválido."""
        # Setup
        message_sender = MagicMock()
        message_sender.send_console_msg = AsyncMock()
        bank_deposit_handler = create_mock_bank_deposit_handler(message_sender=message_sender)

        # Packet muy corto
        data = bytes([43, 1])  # Falta quantity
        session_data = {"user_id": 1}

        task = TaskBankDeposit(
            data,
            message_sender,
            bank_deposit_handler=bank_deposit_handler,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert - debe enviar mensaje de error
        message_sender.send_console_msg.assert_called_once()
        bank_deposit_handler.handle.assert_not_called()

    async def test_deposit_without_handler(self) -> None:
        """Test sin handler."""
        # Setup
        message_sender = MagicMock()
        message_sender.send_console_msg = AsyncMock()

        data = bytes([43, 1, 5, 0])
        session_data = {"user_id": 1}

        task = TaskBankDeposit(
            data,
            message_sender,
            bank_deposit_handler=None,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert
        message_sender.send_console_msg.assert_called_with("Error al depositar en el banco")
