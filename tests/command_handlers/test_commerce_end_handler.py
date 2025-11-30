"""Tests para CommerceEndCommandHandler."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.command_handlers.commerce_end_handler import CommerceEndCommandHandler
from src.commands.commerce_end_command import CommerceEndCommand
from src.commands.walk_command import WalkCommand


@pytest.fixture
def mock_message_sender() -> MagicMock:
    """Mock de MessageSender."""
    sender = MagicMock()
    sender.connection = MagicMock()
    sender.connection.address = "127.0.0.1:12345"
    sender.send_commerce_end = AsyncMock()
    return sender


@pytest.mark.asyncio
async def test_handle_commerce_end_success(mock_message_sender: MagicMock) -> None:
    """Test cerrar comercio exitoso."""
    handler = CommerceEndCommandHandler(message_sender=mock_message_sender)

    command = CommerceEndCommand()
    result = await handler.handle(command)

    assert result.success is True
    mock_message_sender.send_commerce_end.assert_called_once()


@pytest.mark.asyncio
async def test_handle_invalid_command(mock_message_sender: MagicMock) -> None:
    """Test con comando inválido."""
    handler = CommerceEndCommandHandler(message_sender=mock_message_sender)

    invalid_command = WalkCommand(user_id=1, heading=2)
    result = await handler.handle(invalid_command)

    assert result.success is False


@pytest.mark.asyncio
async def test_handle_error_handling(mock_message_sender: MagicMock) -> None:
    """Test manejo de errores."""
    mock_message_sender.send_commerce_end = AsyncMock(side_effect=Exception("Error"))

    handler = CommerceEndCommandHandler(message_sender=mock_message_sender)

    command = CommerceEndCommand()
    result = await handler.handle(command)

    assert result.success is False
    assert "error" in result.error_message.lower()
