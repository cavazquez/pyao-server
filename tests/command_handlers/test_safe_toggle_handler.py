"""Tests para SafeToggleCommandHandler."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.command_handlers.safe_toggle_handler import SafeToggleCommandHandler
from src.commands.safe_toggle_command import SafeToggleCommand
from src.commands.walk_command import WalkCommand


@pytest.fixture
def mock_player_repo() -> MagicMock:
    """Mock de PlayerRepository."""
    repo = MagicMock()
    repo.get_safe_mode = AsyncMock(return_value=False)
    repo.set_safe_mode = AsyncMock()
    return repo


@pytest.fixture
def mock_message_sender() -> MagicMock:
    """Mock de MessageSender."""
    sender = MagicMock()
    sender.send_console_msg = AsyncMock()
    return sender


@pytest.mark.asyncio
async def test_handle_activate_safe_mode(
    mock_player_repo: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test activar modo seguro."""
    mock_player_repo.get_safe_mode = AsyncMock(return_value=False)

    handler = SafeToggleCommandHandler(
        player_repo=mock_player_repo,
        message_sender=mock_message_sender,
    )

    command = SafeToggleCommand(user_id=1)
    result = await handler.handle(command)

    assert result.success is True
    mock_player_repo.set_safe_mode.assert_called_once_with(1, True)


@pytest.mark.asyncio
async def test_handle_deactivate_safe_mode(
    mock_player_repo: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test desactivar modo seguro."""
    mock_player_repo.get_safe_mode = AsyncMock(return_value=True)

    handler = SafeToggleCommandHandler(
        player_repo=mock_player_repo,
        message_sender=mock_message_sender,
    )

    command = SafeToggleCommand(user_id=1)
    result = await handler.handle(command)

    assert result.success is True
    mock_player_repo.set_safe_mode.assert_called_once_with(1, False)


@pytest.mark.asyncio
async def test_handle_invalid_command(
    mock_player_repo: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test con comando inválido."""
    handler = SafeToggleCommandHandler(
        player_repo=mock_player_repo,
        message_sender=mock_message_sender,
    )

    invalid_command = WalkCommand(user_id=1, heading=2)
    result = await handler.handle(invalid_command)

    assert result.success is False


@pytest.mark.asyncio
async def test_handle_sends_confirmation_message(
    mock_player_repo: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test que se envía mensaje de confirmación."""
    mock_player_repo.get_safe_mode = AsyncMock(return_value=False)

    handler = SafeToggleCommandHandler(
        player_repo=mock_player_repo,
        message_sender=mock_message_sender,
    )

    command = SafeToggleCommand(user_id=1)
    result = await handler.handle(command)

    assert result.success is True
    mock_message_sender.send_console_msg.assert_called_once()
    call_args = mock_message_sender.send_console_msg.call_args
    assert "ACTIVADO" in call_args[0][0]