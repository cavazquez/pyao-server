"""Tests para UseItemCommandHandler."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.command_handlers.use_item_handler import UseItemCommandHandler
from src.commands.use_item_command import UseItemCommand
from src.commands.walk_command import WalkCommand


@pytest.fixture
def mock_player_repo() -> MagicMock:
    """Mock de PlayerRepository."""
    repo = MagicMock()
    repo.redis = MagicMock()
    repo.get_stats = AsyncMock(return_value={"min_hp": 50, "max_hp": 100})
    repo.is_working = AsyncMock(return_value=False)
    repo.set_working = AsyncMock()
    repo.is_sailing = AsyncMock(return_value=False)
    repo.set_sailing = AsyncMock()
    repo.get_position = AsyncMock(return_value={"map": 1, "x": 50, "y": 50})
    return repo


@pytest.fixture
def mock_item_catalog() -> MagicMock:
    """Mock de ItemCatalog."""
    return MagicMock()


@pytest.fixture
def mock_message_sender() -> MagicMock:
    """Mock de MessageSender."""
    sender = MagicMock()
    sender.send_console_msg = AsyncMock()
    sender.send_update_user_stats = AsyncMock()
    return sender


@pytest.mark.asyncio
async def test_handle_invalid_command(
    mock_player_repo: MagicMock,
    mock_item_catalog: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test con comando inválido."""
    handler = UseItemCommandHandler(
        player_repo=mock_player_repo,
        map_resources=None,
        account_repo=None,
        message_sender=mock_message_sender,
        item_catalog=mock_item_catalog,
    )

    invalid_command = WalkCommand(user_id=1, heading=2)
    result = await handler.handle(invalid_command)

    assert result.success is False


@pytest.mark.asyncio
async def test_handle_empty_slot(
    mock_player_repo: MagicMock,
    mock_item_catalog: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test usar item con slot vacío."""
    # Mock del inventory_repo que retorna slot vacío
    with patch("src.command_handlers.use_item_handler.InventoryRepository") as mock_inv_repo_class:
        mock_inv_repo = MagicMock()
        mock_inv_repo.get_slot = AsyncMock(return_value=None)
        mock_inv_repo_class.return_value = mock_inv_repo

        handler = UseItemCommandHandler(
            player_repo=mock_player_repo,
            map_resources=None,
            account_repo=None,
            message_sender=mock_message_sender,
            item_catalog=mock_item_catalog,
        )

        command = UseItemCommand(user_id=1, slot=5, username="testuser")
        result = await handler.handle(command)

        assert result.success is False


@pytest.mark.asyncio
async def test_handle_no_player_repo(
    mock_item_catalog: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test usar item sin PlayerRepository."""
    handler = UseItemCommandHandler(
        player_repo=None,  # type: ignore[arg-type]
        map_resources=None,
        account_repo=None,
        message_sender=mock_message_sender,
        item_catalog=mock_item_catalog,
    )

    command = UseItemCommand(user_id=1, slot=5, username="testuser")
    result = await handler.handle(command)

    assert result.success is False
