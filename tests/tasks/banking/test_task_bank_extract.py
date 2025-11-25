"""Tests para TaskBankExtract."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.commands.bank_extract_command import BankExtractCommand
from src.commands.base import CommandResult
from src.tasks.banking.task_bank_extract import TaskBankExtract


def create_mock_bank_extract_handler(
    bank_repo: MagicMock | None = None,
    inventory_repo: MagicMock | None = None,
    player_repo: MagicMock | None = None,
    message_sender: MagicMock | None = None,
) -> MagicMock:
    """Crea un mock de BankExtractCommandHandler con las dependencias especificadas."""
    handler = MagicMock()
    handler.bank_repo = bank_repo or MagicMock()
    handler.inventory_repo = inventory_repo or MagicMock()
    handler.player_repo = player_repo or MagicMock()
    handler.message_sender = message_sender or MagicMock()
    handler.handle = AsyncMock()
    return handler


@pytest.mark.asyncio
class TestTaskBankExtract:
    """Tests para TaskBankExtract."""

    async def test_extract_success(self) -> None:
        """Test de extracción exitosa."""
        # Setup
        message_sender = MagicMock()
        message_sender.send_console_msg = AsyncMock()
        message_sender.send_change_inventory_slot = AsyncMock()
        message_sender.send_change_bank_slot = AsyncMock()

        bank_extract_handler = create_mock_bank_extract_handler(message_sender=message_sender)
        bank_extract_handler.handle.return_value = CommandResult.ok(
            data={"item_id": 10, "quantity": 5, "bank_slot": 1, "inventory_slots": [(1, 5)]}
        )

        # Packet: BANK_EXTRACT_ITEM + slot=1 + quantity=5
        data = bytes([41, 1, 5, 0])  # quantity en little-endian
        session_data = {"user_id": 1}

        task = TaskBankExtract(
            data,
            message_sender,
            bank_extract_handler=bank_extract_handler,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert
        bank_extract_handler.handle.assert_called_once()
        call_args = bank_extract_handler.handle.call_args[0][0]
        assert isinstance(call_args, BankExtractCommand)
        assert call_args.user_id == 1
        assert call_args.slot == 1
        assert call_args.quantity == 5

    async def test_extract_without_session(self) -> None:
        """Test de extracción sin sesión activa."""
        # Setup
        message_sender = MagicMock()
        bank_extract_handler = create_mock_bank_extract_handler(message_sender=message_sender)

        data = bytes([41, 1, 1, 0])
        session_data = {}  # Sin user_id

        task = TaskBankExtract(
            data,
            message_sender,
            bank_extract_handler=bank_extract_handler,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert - no debe hacer nada
        bank_extract_handler.handle.assert_not_called()

    async def test_extract_invalid_quantity(self) -> None:
        """Test de extracción con cantidad inválida."""
        # Setup
        message_sender = MagicMock()
        message_sender.send_console_msg = AsyncMock()
        bank_extract_handler = create_mock_bank_extract_handler(message_sender=message_sender)

        # Packet con cantidad 0
        data = bytes([41, 1, 0, 0])
        session_data = {"user_id": 1}

        task = TaskBankExtract(
            data,
            message_sender,
            bank_extract_handler=bank_extract_handler,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert - El validador da un mensaje más descriptivo
        message_sender.send_console_msg.assert_called_once()
        call_args = message_sender.send_console_msg.call_args[0][0]
        assert "Cantidad inválida" in call_args
        bank_extract_handler.handle.assert_not_called()

    async def test_extract_empty_slot(self) -> None:
        """Test de extracción desde slot vacío."""
        # Setup
        message_sender = MagicMock()
        message_sender.send_console_msg = AsyncMock()

        bank_extract_handler = create_mock_bank_extract_handler(message_sender=message_sender)
        bank_extract_handler.handle.return_value = CommandResult.error(
            "No hay ningún item en ese slot del banco"
        )

        data = bytes([41, 1, 5, 0])
        session_data = {"user_id": 1}

        task = TaskBankExtract(
            data,
            message_sender,
            bank_extract_handler=bank_extract_handler,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert
        bank_extract_handler.handle.assert_called_once()

    async def test_extract_insufficient_quantity(self) -> None:
        """Test de extracción con cantidad insuficiente."""
        # Setup
        message_sender = MagicMock()
        message_sender.send_console_msg = AsyncMock()

        bank_extract_handler = create_mock_bank_extract_handler(message_sender=message_sender)
        bank_extract_handler.handle.return_value = CommandResult.error(
            "Solo tienes 3 items en ese slot del banco"
        )

        # Intentar extraer 5 items
        data = bytes([41, 1, 5, 0])
        session_data = {"user_id": 1}

        task = TaskBankExtract(
            data,
            message_sender,
            bank_extract_handler=bank_extract_handler,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert
        bank_extract_handler.handle.assert_called_once()

    async def test_extract_fails(self) -> None:
        """Test cuando falla la extracción del banco."""
        # Setup
        message_sender = MagicMock()
        message_sender.send_console_msg = AsyncMock()

        bank_extract_handler = create_mock_bank_extract_handler(message_sender=message_sender)
        bank_extract_handler.handle.return_value = CommandResult.error("Error al extraer del banco")

        data = bytes([41, 1, 5, 0])
        session_data = {"user_id": 1}

        task = TaskBankExtract(
            data,
            message_sender,
            bank_extract_handler=bank_extract_handler,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert
        bank_extract_handler.handle.assert_called_once()

    async def test_extract_inventory_full(self) -> None:
        """Test de extracción cuando el inventario está lleno."""
        # Setup
        message_sender = MagicMock()
        message_sender.send_console_msg = AsyncMock()

        bank_extract_handler = create_mock_bank_extract_handler(message_sender=message_sender)
        bank_extract_handler.handle.return_value = CommandResult.error(
            "No tienes espacio en el inventario"
        )

        data = bytes([41, 1, 5, 0])
        session_data = {"user_id": 1}

        task = TaskBankExtract(
            data,
            message_sender,
            bank_extract_handler=bank_extract_handler,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert
        bank_extract_handler.handle.assert_called_once()

    async def test_extract_invalid_packet_size(self) -> None:
        """Test con packet de tamaño inválido."""
        # Setup
        message_sender = MagicMock()
        message_sender.send_console_msg = AsyncMock()
        bank_extract_handler = create_mock_bank_extract_handler(message_sender=message_sender)

        # Packet muy corto
        data = bytes([41, 1])  # Falta quantity
        session_data = {"user_id": 1}

        task = TaskBankExtract(
            data,
            message_sender,
            bank_extract_handler=bank_extract_handler,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert - debe enviar mensaje de error
        message_sender.send_console_msg.assert_called_once()
        bank_extract_handler.handle.assert_not_called()

    async def test_extract_without_handler(self) -> None:
        """Test sin handler."""
        # Setup
        message_sender = MagicMock()
        message_sender.send_console_msg = AsyncMock()

        data = bytes([41, 1, 5, 0])
        session_data = {"user_id": 1}

        task = TaskBankExtract(
            data,
            message_sender,
            bank_extract_handler=None,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert
        message_sender.send_console_msg.assert_called_with("Error al extraer del banco")

    async def test_extract_multiple_slots(self) -> None:
        """Test de extracción que llena múltiples slots del inventario."""
        # Setup
        message_sender = MagicMock()
        message_sender.send_console_msg = AsyncMock()
        message_sender.send_change_inventory_slot = AsyncMock()
        message_sender.send_change_bank_slot = AsyncMock()

        bank_extract_handler = create_mock_bank_extract_handler(message_sender=message_sender)
        bank_extract_handler.handle.return_value = CommandResult.ok(
            data={
                "item_id": 10,
                "quantity": 10,
                "bank_slot": 1,
                "inventory_slots": [(1, 5), (2, 5)],
            }
        )

        data = bytes([41, 1, 10, 0])
        session_data = {"user_id": 1}

        task = TaskBankExtract(
            data,
            message_sender,
            bank_extract_handler=bank_extract_handler,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert - debe llamar al handler (la lógica de múltiples slots está en el handler)
        bank_extract_handler.handle.assert_called_once()
