"""Tests para RequestPositionUpdateCommandHandler."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.command_handlers.request_position_update_handler import (
    RequestPositionUpdateCommandHandler,
)
from src.commands.request_position_update_command import RequestPositionUpdateCommand
from src.commands.walk_command import WalkCommand


@pytest.fixture
def mock_player_repo() -> MagicMock:
    """Mock de PlayerRepository."""
    repo = MagicMock()
    repo.get_position = AsyncMock(return_value={"x": 100, "y": 200, "map": 1})
    return repo


@pytest.fixture
def mock_message_sender() -> MagicMock:
    """Mock de MessageSender."""
    sender = MagicMock()
    sender.send_pos_update = AsyncMock()
    return sender


@pytest.mark.asyncio
async def test_handle_request_position_success(
    mock_player_repo: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test solicitud de posición exitosa."""
    handler = RequestPositionUpdateCommandHandler(
        player_repo=mock_player_repo,
        message_sender=mock_message_sender,
    )

    command = RequestPositionUpdateCommand(user_id=1)
    result = await handler.handle(command)

    assert result.success is True
    assert result.data["x"] == 100
    assert result.data["y"] == 200
    assert result.data["map"] == 1
    mock_message_sender.send_pos_update.assert_called_once_with(100, 200)


@pytest.mark.asyncio
async def test_handle_no_position_default(
    mock_player_repo: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test cuando no hay posición, usa valores por defecto."""
    mock_player_repo.get_position = AsyncMock(return_value=None)

    handler = RequestPositionUpdateCommandHandler(
        player_repo=mock_player_repo,
        message_sender=mock_message_sender,
    )

    command = RequestPositionUpdateCommand(user_id=1)
    result = await handler.handle(command)

    assert result.success is True
    assert result.data["x"] == 50
    assert result.data["y"] == 50
    assert result.data["default"] is True
    mock_message_sender.send_pos_update.assert_called_once_with(50, 50)


@pytest.mark.asyncio
async def test_handle_invalid_command(
    mock_player_repo: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test con comando inválido."""
    handler = RequestPositionUpdateCommandHandler(
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
    mock_player_repo.get_position = AsyncMock(side_effect=Exception("Error"))

    handler = RequestPositionUpdateCommandHandler(
        player_repo=mock_player_repo,
        message_sender=mock_message_sender,
    )

    command = RequestPositionUpdateCommand(user_id=1)
    result = await handler.handle(command)

    assert result.success is False
    assert "error" in result.error_message.lower()
