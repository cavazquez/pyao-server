"""Tests para RequestStatsCommandHandler."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.command_handlers.request_stats_handler import RequestStatsCommandHandler
from src.commands.request_stats_command import RequestStatsCommand
from src.commands.walk_command import WalkCommand


@pytest.fixture
def mock_player_repo() -> MagicMock:
    """Mock de PlayerRepository."""
    repo = MagicMock()
    repo.get_stats = AsyncMock(
        return_value={
            "level": 5,
            "experience": 1000,
            "elu": 2000,
            "min_hp": 80,
            "max_hp": 100,
            "min_mana": 50,
            "max_mana": 75,
            "min_sta": 60,
            "max_sta": 80,
            "gold": 500,
        }
    )
    repo.get_attributes = AsyncMock(
        return_value={
            "strength": 15,
            "agility": 14,
            "intelligence": 13,
            "charisma": 12,
            "constitution": 16,
        }
    )
    repo.get_hunger_thirst = AsyncMock(
        return_value={
            "min_hunger": 80,
            "max_hunger": 100,
            "min_water": 70,
            "max_water": 100,
        }
    )
    return repo


@pytest.fixture
def mock_message_sender() -> MagicMock:
    """Mock de MessageSender."""
    sender = MagicMock()
    sender.send_console_msg = AsyncMock()
    sender.send_multiline_console_msg = AsyncMock()
    return sender


@pytest.mark.asyncio
async def test_handle_request_stats_success(
    mock_player_repo: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test solicitud de estadísticas exitosa."""
    handler = RequestStatsCommandHandler(
        player_repo=mock_player_repo,
        message_sender=mock_message_sender,
    )

    command = RequestStatsCommand(user_id=1)
    result = await handler.handle(command)

    assert result.success is True
    assert "stats" in result.data
    assert "attributes" in result.data
    assert "hunger_thirst" in result.data
    mock_message_sender.send_multiline_console_msg.assert_called_once()


@pytest.mark.asyncio
async def test_handle_no_stats(
    mock_player_repo: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test cuando no hay stats disponibles."""
    mock_player_repo.get_stats = AsyncMock(return_value=None)

    handler = RequestStatsCommandHandler(
        player_repo=mock_player_repo,
        message_sender=mock_message_sender,
    )

    command = RequestStatsCommand(user_id=1)
    result = await handler.handle(command)

    assert result.success is False
    assert "estadísticas" in result.error_message.lower()


@pytest.mark.asyncio
async def test_handle_no_attributes(
    mock_player_repo: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test cuando no hay atributos disponibles."""
    mock_player_repo.get_attributes = AsyncMock(return_value=None)

    handler = RequestStatsCommandHandler(
        player_repo=mock_player_repo,
        message_sender=mock_message_sender,
    )

    command = RequestStatsCommand(user_id=1)
    result = await handler.handle(command)

    assert result.success is False
    assert "atributos" in result.error_message.lower()


@pytest.mark.asyncio
async def test_handle_no_hunger_thirst(
    mock_player_repo: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test cuando no hay hambre/sed disponibles."""
    mock_player_repo.get_hunger_thirst = AsyncMock(return_value=None)

    handler = RequestStatsCommandHandler(
        player_repo=mock_player_repo,
        message_sender=mock_message_sender,
    )

    command = RequestStatsCommand(user_id=1)
    result = await handler.handle(command)

    assert result.success is False
    assert "hambre" in result.error_message.lower() or "sed" in result.error_message.lower()


@pytest.mark.asyncio
async def test_handle_invalid_command(
    mock_player_repo: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test con comando inválido."""
    handler = RequestStatsCommandHandler(
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
    mock_player_repo.get_stats = AsyncMock(side_effect=Exception("Error"))

    handler = RequestStatsCommandHandler(
        player_repo=mock_player_repo,
        message_sender=mock_message_sender,
    )

    command = RequestStatsCommand(user_id=1)
    result = await handler.handle(command)

    assert result.success is False
    assert "error" in result.error_message.lower()
