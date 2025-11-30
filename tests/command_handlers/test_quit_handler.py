"""Tests para QuitCommandHandler."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.command_handlers.quit_handler import QuitCommandHandler
from src.commands.quit_command import QuitCommand
from src.commands.walk_command import WalkCommand


@pytest.fixture
def mock_player_repo() -> MagicMock:
    """Mock de PlayerRepository."""
    repo = MagicMock()
    repo.get_position = AsyncMock(return_value={"map": 1})
    return repo


@pytest.fixture
def mock_map_manager() -> MagicMock:
    """Mock de MapManager."""
    manager = MagicMock()
    manager.get_all_message_senders_in_map = MagicMock(return_value=[])
    manager.remove_player_from_all_maps = MagicMock()
    return manager


@pytest.fixture
def mock_message_sender() -> MagicMock:
    """Mock de MessageSender."""
    sender = MagicMock()
    sender.connection = MagicMock()
    sender.connection.address = "127.0.0.1:12345"
    sender.connection.close = MagicMock()
    sender.connection.wait_closed = AsyncMock()
    sender.send_character_remove = AsyncMock()
    return sender


@pytest.mark.asyncio
async def test_handle_quit_success(
    mock_player_repo: MagicMock,
    mock_map_manager: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test desconexión exitosa."""
    handler = QuitCommandHandler(
        player_repo=mock_player_repo,
        map_manager=mock_map_manager,
        message_sender=mock_message_sender,
    )

    command = QuitCommand(user_id=1, username="TestUser")
    result = await handler.handle(command)

    assert result.success is True
    assert result.data["user_id"] == 1
    assert result.data["username"] == "TestUser"
    mock_map_manager.remove_player_from_all_maps.assert_called_once_with(1)
    mock_message_sender.connection.close.assert_called_once()


@pytest.mark.asyncio
async def test_handle_quit_without_repo(
    mock_map_manager: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test desconexión sin player_repo."""
    handler = QuitCommandHandler(
        player_repo=None,
        map_manager=mock_map_manager,
        message_sender=mock_message_sender,
    )

    command = QuitCommand(user_id=1, username="TestUser")
    result = await handler.handle(command)

    assert result.success is True
    mock_message_sender.connection.close.assert_called_once()


@pytest.mark.asyncio
async def test_handle_quit_cleanup_pets(
    mock_player_repo: MagicMock,
    mock_map_manager: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test desconexión con limpieza de mascotas."""
    mock_summon_service = MagicMock()
    mock_summon_service.remove_all_player_pets = AsyncMock(return_value=["pet1", "pet2"])

    mock_npc_service = MagicMock()
    mock_npc_service.npc_repository = MagicMock()
    mock_npc_service.npc_repository.get_all_npcs = AsyncMock(return_value=[])
    mock_npc_service.remove_npc = AsyncMock()

    handler = QuitCommandHandler(
        player_repo=mock_player_repo,
        map_manager=mock_map_manager,
        message_sender=mock_message_sender,
        npc_service=mock_npc_service,
        summon_service=mock_summon_service,
    )

    command = QuitCommand(user_id=1, username="TestUser")
    result = await handler.handle(command)

    assert result.success is True
    mock_summon_service.remove_all_player_pets.assert_called_once_with(1)


@pytest.mark.asyncio
async def test_handle_invalid_command(
    mock_player_repo: MagicMock,
    mock_map_manager: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test con comando inválido."""
    handler = QuitCommandHandler(
        player_repo=mock_player_repo,
        map_manager=mock_map_manager,
        message_sender=mock_message_sender,
    )

    invalid_command = WalkCommand(user_id=1, heading=2)
    result = await handler.handle(invalid_command)

    assert result.success is False


@pytest.mark.asyncio
async def test_handle_error_handling(
    mock_player_repo: MagicMock,
    mock_map_manager: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test manejo de errores."""
    mock_message_sender.connection.close = MagicMock(side_effect=Exception("Error"))

    handler = QuitCommandHandler(
        player_repo=mock_player_repo,
        map_manager=mock_map_manager,
        message_sender=mock_message_sender,
    )

    command = QuitCommand(user_id=1, username="TestUser")
    result = await handler.handle(command)

    assert result.success is False
    assert "error" in result.error_message.lower()
