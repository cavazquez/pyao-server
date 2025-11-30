"""Tests para BankEndCommandHandler."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.command_handlers.bank_end_handler import BankEndCommandHandler
from src.commands.bank_end_command import BankEndCommand
from src.commands.walk_command import WalkCommand


@pytest.fixture
def mock_message_sender() -> MagicMock:
    """Mock de MessageSender."""
    sender = MagicMock()
    sender.send_bank_end = AsyncMock()
    return sender


@pytest.mark.asyncio
async def test_handle_bank_end_with_user_id(mock_message_sender: MagicMock) -> None:
    """Test cerrar banco con user_id."""
    handler = BankEndCommandHandler(message_sender=mock_message_sender)

    command = BankEndCommand(user_id=1)
    result = await handler.handle(command)

    assert result.success is True
    assert result.data["user_id"] == 1
    mock_message_sender.send_bank_end.assert_called_once()


@pytest.mark.asyncio
async def test_handle_bank_end_pre_login(mock_message_sender: MagicMock) -> None:
    """Test cerrar banco sin sesión (pre-login)."""
    handler = BankEndCommandHandler(message_sender=mock_message_sender)

    command = BankEndCommand(user_id=None)
    result = await handler.handle(command)

    assert result.success is True
    assert result.data["pre_login"] is True
    # No debe enviar mensaje al cliente si es pre-login
    mock_message_sender.send_bank_end.assert_not_called()


@pytest.mark.asyncio
async def test_handle_invalid_command(mock_message_sender: MagicMock) -> None:
    """Test con comando inválido."""
    handler = BankEndCommandHandler(message_sender=mock_message_sender)

    invalid_command = WalkCommand(user_id=1, heading=2)
    result = await handler.handle(invalid_command)

    assert result.success is False


@pytest.mark.asyncio
async def test_handle_error_handling(mock_message_sender: MagicMock) -> None:
    """Test manejo de errores."""
    mock_message_sender.send_bank_end = AsyncMock(side_effect=Exception("Error"))

    handler = BankEndCommandHandler(message_sender=mock_message_sender)

    command = BankEndCommand(user_id=1)
    result = await handler.handle(command)

    assert result.success is False
    assert "error" in result.error_message.lower()
