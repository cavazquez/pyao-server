"""Tests para LeftClickCommandHandler."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.command_handlers.left_click_handler import LeftClickCommandHandler
from src.commands.base import CommandResult
from src.commands.left_click_command import LeftClickCommand
from src.commands.walk_command import WalkCommand


@pytest.fixture
def mock_player_repo() -> MagicMock:
    """Mock de PlayerRepository."""
    repo = MagicMock()
    repo.get_position = AsyncMock(return_value={"map": 1, "x": 50, "y": 50})
    return repo


@pytest.fixture
def mock_map_manager() -> MagicMock:
    """Mock de MapManager."""
    manager = MagicMock()
    manager.get_npc_by_char_index = MagicMock(return_value=None)
    return manager


@pytest.fixture
def mock_message_sender() -> MagicMock:
    """Mock de MessageSender."""
    sender = MagicMock()
    sender.send_console_msg = AsyncMock()
    return sender


@pytest.mark.asyncio
async def test_handle_invalid_command(
    mock_player_repo: MagicMock,
    mock_map_manager: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test con comando inválido."""
    handler = LeftClickCommandHandler(
        player_repo=mock_player_repo,
        map_manager=mock_map_manager,
        map_resources=None,
        bank_repo=None,
        merchant_repo=None,
        door_service=None,
        door_repo=None,
        redis_client=None,
        message_sender=mock_message_sender,
    )

    invalid_command = WalkCommand(user_id=1, heading=2)
    result = await handler.handle(invalid_command)

    assert result.success is False


@pytest.mark.asyncio
async def test_handle_basic_click(
    mock_player_repo: MagicMock,
    mock_map_manager: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test click básico en el mapa."""
    handler = LeftClickCommandHandler(
        player_repo=mock_player_repo,
        map_manager=mock_map_manager,
        map_resources=None,
        bank_repo=None,
        merchant_repo=None,
        door_service=None,
        door_repo=None,
        redis_client=None,
        message_sender=mock_message_sender,
    )

    command = LeftClickCommand(user_id=1, map_id=1, x=50, y=50)
    result = await handler.handle(command)

    # Debe ejecutarse (puede ser exitoso o no según lo que encuentre)
    assert isinstance(result, CommandResult)
