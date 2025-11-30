"""Tests para AyudaCommandHandler."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.command_handlers.ayuda_handler import AyudaCommandHandler
from src.commands.ayuda_command import AyudaCommand
from src.commands.walk_command import WalkCommand


@pytest.fixture
def mock_message_sender() -> MagicMock:
    """Mock de MessageSender."""
    sender = MagicMock()
    sender.connection = MagicMock()
    sender.connection.address = "127.0.0.1:12345"
    sender.send_multiline_console_msg = AsyncMock()
    return sender


@pytest.mark.asyncio
async def test_handle_ayuda_success(mock_message_sender: MagicMock) -> None:
    """Test comando ayuda exitoso."""
    handler = AyudaCommandHandler(message_sender=mock_message_sender)

    command = AyudaCommand()
    result = await handler.handle(command)

    assert result.success is True
    assert "help_message" in result.data
    assert "Comandos Disponibles" in result.data["help_message"]
    mock_message_sender.send_multiline_console_msg.assert_called_once()


@pytest.mark.asyncio
async def test_handle_invalid_command(mock_message_sender: MagicMock) -> None:
    """Test con comando inválido."""
    handler = AyudaCommandHandler(message_sender=mock_message_sender)

    invalid_command = WalkCommand(user_id=1, heading=2)
    result = await handler.handle(invalid_command)

    assert result.success is False


@pytest.mark.asyncio
async def test_handle_error_handling(mock_message_sender: MagicMock) -> None:
    """Test manejo de errores."""
    mock_message_sender.send_multiline_console_msg = AsyncMock(side_effect=Exception("Error"))

    handler = AyudaCommandHandler(message_sender=mock_message_sender)

    command = AyudaCommand()
    result = await handler.handle(command)

    assert result.success is False
    assert "error" in result.error_message.lower()
