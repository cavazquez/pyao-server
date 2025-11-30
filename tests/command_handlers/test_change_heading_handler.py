"""Tests para ChangeHeadingCommandHandler."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.command_handlers.change_heading_handler import (
    SHIP_BODY_ID,
    ChangeHeadingCommandHandler,
)
from src.commands.change_heading_command import ChangeHeadingCommand
from src.commands.walk_command import WalkCommand


@pytest.fixture
def mock_player_repo() -> MagicMock:
    """Mock de PlayerRepository."""
    repo = MagicMock()
    repo.set_heading = AsyncMock()
    repo.is_sailing = AsyncMock(return_value=False)
    repo.get_position = AsyncMock(return_value={"map": 1, "x": 50, "y": 50, "heading": 3})
    return repo


@pytest.fixture
def mock_account_repo() -> MagicMock:
    """Mock de AccountRepository."""
    repo = MagicMock()
    repo.get_account = AsyncMock(return_value={"char_race": 2, "char_head": 16})
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
    sender.send_character_change = AsyncMock()
    return sender


@pytest.mark.asyncio
async def test_handle_valid_command(
    mock_player_repo: MagicMock,
    mock_map_manager: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test cambio de dirección válido."""
    handler = ChangeHeadingCommandHandler(
        player_repo=mock_player_repo,
        account_repo=None,
        map_manager=mock_map_manager,
        message_sender=mock_message_sender,
    )

    command = ChangeHeadingCommand(user_id=1, heading=2)
    result = await handler.handle(command)

    assert result.success is True
    mock_player_repo.set_heading.assert_called_once_with(1, 2)
    mock_message_sender.send_character_change.assert_called_once()


@pytest.mark.asyncio
async def test_handle_invalid_command(
    mock_player_repo: MagicMock,
    mock_map_manager: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test con comando inválido."""
    handler = ChangeHeadingCommandHandler(
        player_repo=mock_player_repo,
        account_repo=None,
        map_manager=mock_map_manager,
        message_sender=mock_message_sender,
    )

    # Pasar un comando de otro tipo
    invalid_command = WalkCommand(user_id=1, heading=2)
    result = await handler.handle(invalid_command)

    assert result.success is False
    assert "inválido" in result.error_message.lower()


@pytest.mark.asyncio
async def test_handle_with_sailing(
    mock_player_repo: MagicMock,
    mock_map_manager: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test cambio de dirección cuando está navegando."""
    mock_player_repo.is_sailing = AsyncMock(return_value=True)

    handler = ChangeHeadingCommandHandler(
        player_repo=mock_player_repo,
        account_repo=None,
        map_manager=mock_map_manager,
        message_sender=mock_message_sender,
    )

    command = ChangeHeadingCommand(user_id=1, heading=1)
    result = await handler.handle(command)

    assert result.success is True
    # Debe usar el body de barco
    call_args = mock_message_sender.send_character_change.call_args
    assert call_args[1]["body"] == SHIP_BODY_ID
    assert call_args[1]["head"] == 0


@pytest.mark.asyncio
async def test_handle_with_account_data(
    mock_player_repo: MagicMock,
    mock_account_repo: MagicMock,
    mock_map_manager: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test cambio de dirección con datos de cuenta."""
    handler = ChangeHeadingCommandHandler(
        player_repo=mock_player_repo,
        account_repo=mock_account_repo,
        map_manager=mock_map_manager,
        message_sender=mock_message_sender,
        session_data={"username": "testuser"},
    )

    command = ChangeHeadingCommand(user_id=1, heading=3)
    result = await handler.handle(command)

    assert result.success is True
    mock_account_repo.get_account.assert_called_once_with("testuser")
    # Debe usar los datos de la cuenta
    call_args = mock_message_sender.send_character_change.call_args
    assert call_args[1]["body"] == 2  # char_race
    assert call_args[1]["head"] == 16  # char_head


@pytest.mark.asyncio
async def test_handle_broadcast_to_other_players(
    mock_player_repo: MagicMock,
    mock_map_manager: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test que hace broadcast a otros jugadores."""
    other_sender = MagicMock()
    other_sender.send_character_change = AsyncMock()
    mock_map_manager.get_all_message_senders_in_map = MagicMock(return_value=[other_sender])

    handler = ChangeHeadingCommandHandler(
        player_repo=mock_player_repo,
        account_repo=None,
        map_manager=mock_map_manager,
        message_sender=mock_message_sender,
    )

    command = ChangeHeadingCommand(user_id=1, heading=4)
    result = await handler.handle(command)

    assert result.success is True
    # Debe enviar a otros jugadores también
    other_sender.send_character_change.assert_called_once()


@pytest.mark.asyncio
async def test_handle_with_zero_body_id(
    mock_player_repo: MagicMock,
    mock_account_repo: MagicMock,
    mock_map_manager: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test que maneja body_id = 0 usando valor por defecto."""
    mock_account_repo.get_account = AsyncMock(return_value={"char_race": 0, "char_head": 15})

    handler = ChangeHeadingCommandHandler(
        player_repo=mock_player_repo,
        account_repo=mock_account_repo,
        map_manager=mock_map_manager,
        message_sender=mock_message_sender,
        session_data={"username": "testuser"},
    )

    command = ChangeHeadingCommand(user_id=1, heading=2)
    result = await handler.handle(command)

    assert result.success is True
    # Debe usar valor por defecto si body es 0
    call_args = mock_message_sender.send_character_change.call_args
    assert call_args[1]["body"] == 1  # Valor por defecto


@pytest.mark.asyncio
async def test_handle_without_map_manager(
    mock_player_repo: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test cambio de dirección sin MapManager."""
    handler = ChangeHeadingCommandHandler(
        player_repo=mock_player_repo,
        account_repo=None,
        map_manager=None,
        message_sender=mock_message_sender,
    )

    command = ChangeHeadingCommand(user_id=1, heading=1)
    result = await handler.handle(command)

    assert result.success is True
    # Debe funcionar sin MapManager, solo no hace broadcast


@pytest.mark.asyncio
async def test_result_contains_data(
    mock_player_repo: MagicMock,
    mock_map_manager: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test que el resultado contiene los datos correctos."""
    handler = ChangeHeadingCommandHandler(
        player_repo=mock_player_repo,
        account_repo=None,
        map_manager=mock_map_manager,
        message_sender=mock_message_sender,
    )

    command = ChangeHeadingCommand(user_id=1, heading=3)
    result = await handler.handle(command)

    assert result.success is True
    assert result.data is not None
    assert result.data["user_id"] == 1
    assert result.data["heading"] == 3
    assert "char_body" in result.data
    assert "char_head" in result.data
