"""Tests para WhisperCommandHandler."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.command_handlers.whisper_handler import WhisperCommandHandler
from src.commands.walk_command import WalkCommand
from src.commands.whisper_command import WhisperCommand


@pytest.fixture
def mock_player_repo() -> MagicMock:
    """Mock de PlayerRepository."""
    return MagicMock()


@pytest.fixture
def mock_map_manager() -> MagicMock:
    """Mock de MapManager."""
    manager = MagicMock()
    manager.find_player_by_username = MagicMock(return_value=None)
    manager.get_player_message_sender = MagicMock(return_value=None)
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
    """Test mensaje simple de susurro."""
    mock_map_manager.find_player_by_username = MagicMock(return_value=2)
    target_sender = MagicMock()
    target_sender.send_console_msg = AsyncMock()
    mock_map_manager.get_player_message_sender = MagicMock(return_value=target_sender)

    handler = WhisperCommandHandler(
        player_repo=mock_player_repo,
        map_manager=mock_map_manager,
        message_sender=mock_message_sender,
        session_data={"username": "testuser"},
    )

    command = WhisperCommand(user_id=1, receiver="destino", message="Hola")
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
    handler = WhisperCommandHandler(
        player_repo=mock_player_repo,
        map_manager=mock_map_manager,
        message_sender=mock_message_sender,
    )

    invalid_command = WalkCommand(user_id=1, heading=2)
    result = await handler.handle(invalid_command)

    assert result.success is False


@pytest.mark.asyncio
async def test_handle_no_map_manager(
    mock_player_repo: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test mensaje sin MapManager."""
    handler = WhisperCommandHandler(
        player_repo=mock_player_repo,
        map_manager=None,
        message_sender=mock_message_sender,
    )

    command = WhisperCommand(user_id=1, receiver="destino", message="Hola")
    result = await handler.handle(command)

    assert result.success is False


@pytest.mark.asyncio
async def test_handle_receiver_not_found(
    mock_player_repo: MagicMock,
    mock_map_manager: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test cuando el receptor no está conectado."""
    mock_map_manager.find_player_by_username = MagicMock(return_value=None)

    handler = WhisperCommandHandler(
        player_repo=mock_player_repo,
        map_manager=mock_map_manager,
        message_sender=mock_message_sender,
    )

    command = WhisperCommand(user_id=1, receiver="ausente", message="Hola")
    result = await handler.handle(command)

    assert result.success is False
    mock_message_sender.send_console_msg.assert_called_once()


@pytest.mark.asyncio
async def test_handle_sender_not_available(
    mock_player_repo: MagicMock,
    mock_map_manager: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test cuando el sender del receptor no está disponible."""
    mock_map_manager.find_player_by_username = MagicMock(return_value=2)
    mock_map_manager.get_player_message_sender = MagicMock(return_value=None)

    handler = WhisperCommandHandler(
        player_repo=mock_player_repo,
        map_manager=mock_map_manager,
        message_sender=mock_message_sender,
    )

    command = WhisperCommand(user_id=1, receiver="destino", message="Hola")
    result = await handler.handle(command)

    assert result.success is False
    mock_message_sender.send_console_msg.assert_called_once()


@pytest.mark.asyncio
async def test_handle_sends_to_target_and_sender(
    mock_player_repo: MagicMock,
    mock_map_manager: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test que el mensaje se envía tanto al receptor como al remitente."""
    mock_map_manager.find_player_by_username = MagicMock(return_value=2)
    target_sender = MagicMock()
    target_sender.send_console_msg = AsyncMock()
    mock_map_manager.get_player_message_sender = MagicMock(return_value=target_sender)

    handler = WhisperCommandHandler(
        player_repo=mock_player_repo,
        map_manager=mock_map_manager,
        message_sender=mock_message_sender,
        session_data={"username": "testuser"},
    )

    command = WhisperCommand(user_id=1, receiver="destino", message="Secreto")
    result = await handler.handle(command)

    assert result.success is True
    target_sender.send_console_msg.assert_called_once()
    mock_message_sender.send_console_msg.assert_called()
    call_args_list = mock_message_sender.send_console_msg.call_args_list
    assert len(call_args_list) >= 1
    call_args = call_args_list[0]
    assert "font_color" in call_args[1] or len(call_args[0]) >= 2


@pytest.mark.asyncio
async def test_handle_empty_username(
    mock_player_repo: MagicMock,
    mock_map_manager: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test mensaje con username vacío usa nombre por defecto."""
    mock_map_manager.find_player_by_username = MagicMock(return_value=2)
    target_sender = MagicMock()
    target_sender.send_console_msg = AsyncMock()
    mock_map_manager.get_player_message_sender = MagicMock(return_value=target_sender)

    handler = WhisperCommandHandler(
        player_repo=mock_player_repo,
        map_manager=mock_map_manager,
        message_sender=mock_message_sender,
        session_data={},
    )

    command = WhisperCommand(user_id=1, receiver="destino", message="Test")
    result = await handler.handle(command)

    assert result.success is True
