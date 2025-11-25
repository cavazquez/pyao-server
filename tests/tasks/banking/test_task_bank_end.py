"""Tests para TaskBankEnd."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.commands.bank_end_command import BankEndCommand
from src.commands.base import CommandResult
from src.tasks.banking.task_bank_end import TaskBankEnd


@pytest.mark.asyncio
class TestTaskBankEnd:
    """Tests para TaskBankEnd."""

    async def test_bank_end_with_session(self) -> None:
        """Test de cerrar banco con sesión activa."""
        # Setup
        message_sender = MagicMock()
        message_sender.send_bank_end = AsyncMock()

        # Mock del handler
        bank_end_handler = MagicMock()
        bank_end_handler.handle = AsyncMock(return_value=CommandResult.ok(data={"user_id": 1}))

        # Packet: BANK_END (solo PacketID)
        data = bytes([0x15])

        session_data = {"user_id": 1}

        task = TaskBankEnd(
            data, message_sender, bank_end_handler=bank_end_handler, session_data=session_data
        )

        # Execute
        await task.execute()

        # Verificar que se llamó al handler
        bank_end_handler.handle.assert_called_once()
        call_args = bank_end_handler.handle.call_args[0][0]
        assert isinstance(call_args, BankEndCommand)
        assert call_args.user_id == 1

    async def test_bank_end_without_session(self) -> None:
        """Test de cerrar banco sin sesión (pre-login)."""
        # Setup
        message_sender = MagicMock()

        # Mock del handler
        bank_end_handler = MagicMock()
        bank_end_handler.handle = AsyncMock(return_value=CommandResult.ok(data={"pre_login": True}))

        data = bytes([0x15])
        session_data = {}  # Sin user_id

        task = TaskBankEnd(
            data, message_sender, bank_end_handler=bank_end_handler, session_data=session_data
        )

        # Execute
        await task.execute()

        # Verificar que se llamó al handler
        bank_end_handler.handle.assert_called_once()
        call_args = bank_end_handler.handle.call_args[0][0]
        assert isinstance(call_args, BankEndCommand)
        assert call_args.user_id is None

    async def test_bank_end_minimal(self) -> None:
        """Test básico de TaskBankEnd."""
        # Setup
        message_sender = MagicMock()
        message_sender.send_bank_end = AsyncMock()

        # Mock del handler que realmente llama a send_bank_end
        async def handle_side_effect(_command):
            await message_sender.send_bank_end()
            return CommandResult.ok(data={"user_id": 42})

        bank_end_handler = MagicMock()
        bank_end_handler.handle = AsyncMock(side_effect=handle_side_effect)

        data = bytes([0x15])
        session_data = {"user_id": 42}

        task = TaskBankEnd(
            data, message_sender, bank_end_handler=bank_end_handler, session_data=session_data
        )

        # Execute - debe completar sin errores
        await task.execute()

        # Verify
        bank_end_handler.handle.assert_called_once()
        message_sender.send_bank_end.assert_called_once()

        # Assert - simplemente verificar que no crashea
        assert task.session_data["user_id"] == 42
