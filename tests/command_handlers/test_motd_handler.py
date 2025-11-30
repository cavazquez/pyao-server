"""Tests para MotdCommandHandler."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.command_handlers.motd_handler import MotdCommandHandler
from src.commands.motd_command import MotdCommand
from src.commands.walk_command import WalkCommand


@pytest.fixture
def mock_server_repo() -> MagicMock:
    """Mock de ServerRepository."""
    repo = MagicMock()
    repo.get_motd = AsyncMock(return_value="Test MOTD message")
    return repo


@pytest.fixture
def mock_message_sender() -> MagicMock:
    """Mock de MessageSender."""
    sender = MagicMock()
    sender.connection = MagicMock()
    sender.connection.address = "127.0.0.1:12345"
    sender.send_multiline_console_msg = AsyncMock()
    return sender


@pytest.mark.asyncio
async def test_handle_motd_success(
    mock_server_repo: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test comando MOTD exitoso."""
    handler = MotdCommandHandler(
        server_repo=mock_server_repo,
        message_sender=mock_message_sender,
    )

    command = MotdCommand()
    result = await handler.handle(command)

    assert result.success is True
    assert result.data["motd"] == "Test MOTD message"
    mock_message_sender.send_multiline_console_msg.assert_called_once()


@pytest.mark.asyncio
async def test_handle_motd_no_repo(mock_message_sender: MagicMock) -> None:
    """Test MOTD cuando no hay repositorio, usa mensaje por defecto."""
    handler = MotdCommandHandler(
        server_repo=None,
        message_sender=mock_message_sender,
    )

    command = MotdCommand()
    result = await handler.handle(command)

    assert result.success is True
    assert "Bienvenido" in result.data["motd"]
    mock_message_sender.send_multiline_console_msg.assert_called_once()


@pytest.mark.asyncio
async def test_handle_invalid_command(
    mock_server_repo: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test con comando inválido."""
    handler = MotdCommandHandler(
        server_repo=mock_server_repo,
        message_sender=mock_message_sender,
    )

    invalid_command = WalkCommand(user_id=1, heading=2)
    result = await handler.handle(invalid_command)

    assert result.success is False


@pytest.mark.asyncio
async def test_handle_error_handling(
    mock_server_repo: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test manejo de errores."""
    mock_server_repo.get_motd = AsyncMock(side_effect=Exception("Error"))

    handler = MotdCommandHandler(
        server_repo=mock_server_repo,
        message_sender=mock_message_sender,
    )

    command = MotdCommand()
    result = await handler.handle(command)

    assert result.success is False
    assert "error" in result.error_message.lower()
