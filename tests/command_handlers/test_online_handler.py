"""Tests para OnlineCommandHandler."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.command_handlers.online_handler import OnlineCommandHandler
from src.commands.online_command import OnlineCommand
from src.commands.walk_command import WalkCommand


@pytest.fixture
def mock_map_manager() -> MagicMock:
    """Mock de MapManager."""
    manager = MagicMock()
    manager.get_all_connected_players = MagicMock(return_value=["player1", "player2", "player3"])
    return manager


@pytest.fixture
def mock_message_sender() -> MagicMock:
    """Mock de MessageSender."""
    sender = MagicMock()
    sender.send_console_msg = AsyncMock()
    sender.send_multiline_console_msg = AsyncMock()
    return sender


@pytest.mark.asyncio
async def test_handle_with_players_online(
    mock_map_manager: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test lista de jugadores online cuando hay jugadores."""
    handler = OnlineCommandHandler(
        map_manager=mock_map_manager,
        message_sender=mock_message_sender,
    )

    command = OnlineCommand(user_id=1)
    result = await handler.handle(command)

    assert result.success is True
    assert result.data["count"] == 3
    mock_message_sender.send_multiline_console_msg.assert_called_once()


@pytest.mark.asyncio
async def test_handle_no_players_online(
    mock_message_sender: MagicMock,
) -> None:
    """Test lista cuando no hay jugadores online."""
    mock_map_manager = MagicMock()
    mock_map_manager.get_all_connected_players = MagicMock(return_value=[])

    handler = OnlineCommandHandler(
        map_manager=mock_map_manager,
        message_sender=mock_message_sender,
    )

    command = OnlineCommand(user_id=1)
    result = await handler.handle(command)

    assert result.success is True
    assert result.data["count"] == 0
    mock_message_sender.send_console_msg.assert_called_once()


@pytest.mark.asyncio
async def test_handle_invalid_command(
    mock_map_manager: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test con comando inválido."""
    handler = OnlineCommandHandler(
        map_manager=mock_map_manager,
        message_sender=mock_message_sender,
    )

    invalid_command = WalkCommand(user_id=1, heading=2)
    result = await handler.handle(invalid_command)

    assert result.success is False


@pytest.mark.asyncio
async def test_handle_error_handling(
    mock_message_sender: MagicMock,
) -> None:
    """Test manejo de errores."""
    mock_map_manager = MagicMock()
    mock_map_manager.get_all_connected_players = MagicMock(side_effect=Exception("Error"))

    handler = OnlineCommandHandler(
        map_manager=mock_map_manager,
        message_sender=mock_message_sender,
    )

    command = OnlineCommand(user_id=1)
    result = await handler.handle(command)

    assert result.success is False
    assert "error" in result.error_message.lower()
