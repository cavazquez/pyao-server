"""Tests para YellCommandHandler."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.command_handlers.yell_handler import YellCommandHandler
from src.commands.yell_command import YellCommand
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
    manager.get_all_message_senders_in_map = MagicMock(return_value=[])
    return manager


@pytest.fixture
def mock_message_sender() -> MagicMock:
    """Mock de MessageSender."""
    sender = MagicMock()
    sender.send_console_msg = AsyncMock()
    return sender


@pytest.mark.asyncio
async def test_handle_simple_message(
    mock_player_repo: MagicMock,
    mock_map_manager: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test mensaje simple de grito."""
    handler = YellCommandHandler(
        player_repo=mock_player_repo,
        map_manager=mock_map_manager,
        message_sender=mock_message_sender,
        session_data={"username": "testuser"},
    )

    command = YellCommand(user_id=1, message="Hola mundo")
    result = await handler.handle(command)

    assert result.success is True
    assert result.data is not None


@pytest.mark.asyncio
async def test_handle_invalid_command(
    mock_player_repo: MagicMock,
    mock_map_manager: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test con comando inválido."""
    handler = YellCommandHandler(
        player_repo=mock_player_repo,
        map_manager=mock_map_manager,
        message_sender=mock_message_sender,
    )

    invalid_command = WalkCommand(user_id=1, heading=2)
    result = await handler.handle(invalid_command)

    assert result.success is False


@pytest.mark.asyncio
async def test_handle_no_position(
    mock_player_repo: MagicMock,
    mock_map_manager: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test mensaje sin posición del jugador."""
    mock_player_repo.get_position = AsyncMock(return_value=None)

    handler = YellCommandHandler(
        player_repo=mock_player_repo,
        map_manager=mock_map_manager,
        message_sender=mock_message_sender,
    )

    command = YellCommand(user_id=1, message="Hola")
    result = await handler.handle(command)

    assert result.success is False


@pytest.mark.asyncio
async def test_handle_no_map_manager(
    mock_player_repo: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test mensaje sin MapManager."""
    handler = YellCommandHandler(
        player_repo=mock_player_repo,
        map_manager=None,
        message_sender=mock_message_sender,
    )

    command = YellCommand(user_id=1, message="Hola")
    result = await handler.handle(command)

    assert result.success is False


@pytest.mark.asyncio
async def test_handle_broadcast_message(
    mock_player_repo: MagicMock,
    mock_map_manager: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test mensaje que se broadcast a otros jugadores."""
    other_sender = MagicMock()
    other_sender.send_console_msg = AsyncMock()
    mock_map_manager.get_all_message_senders_in_map = MagicMock(
        return_value=[mock_message_sender, other_sender]
    )

    handler = YellCommandHandler(
        player_repo=mock_player_repo,
        map_manager=mock_map_manager,
        message_sender=mock_message_sender,
        session_data={"username": "testuser"},
    )

    command = YellCommand(user_id=1, message="Hola a todos")
    result = await handler.handle(command)

    assert result.success is True
    other_sender.send_console_msg.assert_called_once()
    call_args_list = other_sender.send_console_msg.call_args_list
    assert len(call_args_list) >= 1
    call_args = call_args_list[0]
    assert call_args[1]["font_color"] == 4


@pytest.mark.asyncio
async def test_handle_empty_username(
    mock_player_repo: MagicMock,
    mock_map_manager: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test mensaje con username vacío usa nombre por defecto."""
    other_sender = MagicMock()
    other_sender.send_console_msg = AsyncMock()
    mock_map_manager.get_all_message_senders_in_map = MagicMock(
        return_value=[other_sender]
    )

    handler = YellCommandHandler(
        player_repo=mock_player_repo,
        map_manager=mock_map_manager,
        message_sender=mock_message_sender,
        session_data={},
    )

    command = YellCommand(user_id=1, message="Test")
    result = await handler.handle(command)

    assert result.success is True