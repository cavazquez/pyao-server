"""Tests para MeditateCommandHandler."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.command_handlers.meditate_handler import MeditateCommandHandler
from src.commands.meditate_command import MeditateCommand
from src.commands.walk_command import WalkCommand


@pytest.fixture
def mock_player_repo() -> MagicMock:
    """Mock de PlayerRepository."""
    repo = MagicMock()
    repo.is_meditating = AsyncMock(return_value=False)
    repo.set_meditating = AsyncMock()
    return repo


@pytest.fixture
def mock_message_sender() -> MagicMock:
    """Mock de MessageSender."""
    sender = MagicMock()
    sender.send_console_msg = AsyncMock()
    sender.send_meditate_toggle = AsyncMock()
    sender.send_create_fx = AsyncMock()
    return sender


@pytest.mark.asyncio
async def test_handle_start_meditation(
    mock_player_repo: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test iniciar meditación."""
    handler = MeditateCommandHandler(
        player_repo=mock_player_repo,
        message_sender=mock_message_sender,
    )

    command = MeditateCommand(user_id=1)
    result = await handler.handle(command)

    assert result.success is True
    assert result.data["is_meditating"] is True
    mock_player_repo.set_meditating.assert_called_once_with(1, True)  # noqa: FBT003
    mock_message_sender.send_create_fx.assert_called_once()


@pytest.mark.asyncio
async def test_handle_stop_meditation(
    mock_player_repo: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test detener meditación."""
    mock_player_repo.is_meditating = AsyncMock(return_value=True)

    handler = MeditateCommandHandler(
        player_repo=mock_player_repo,
        message_sender=mock_message_sender,
    )

    command = MeditateCommand(user_id=1)
    result = await handler.handle(command)

    assert result.success is True
    assert result.data["is_meditating"] is False
    mock_player_repo.set_meditating.assert_called_once_with(1, False)  # noqa: FBT003


@pytest.mark.asyncio
async def test_handle_invalid_command(
    mock_player_repo: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test con comando inválido."""
    handler = MeditateCommandHandler(
        player_repo=mock_player_repo,
        message_sender=mock_message_sender,
    )

    invalid_command = WalkCommand(user_id=1, heading=2)
    result = await handler.handle(invalid_command)

    assert result.success is False


@pytest.mark.asyncio
async def test_handle_error_handling(
    mock_player_repo: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test manejo de errores."""
    mock_player_repo.is_meditating = AsyncMock(side_effect=Exception("Error"))

    handler = MeditateCommandHandler(
        player_repo=mock_player_repo,
        message_sender=mock_message_sender,
    )

    command = MeditateCommand(user_id=1)
    result = await handler.handle(command)

    assert result.success is False
    assert "error" in result.error_message.lower()
