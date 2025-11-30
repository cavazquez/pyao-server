"""Tests para PartyMessageCommandHandler."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.command_handlers.party_message_handler import PartyMessageCommandHandler
from src.commands.party_message_command import PartyMessageCommand
from src.commands.walk_command import WalkCommand


@pytest.fixture
def mock_party_service() -> MagicMock:
    """Mock de PartyService."""
    return MagicMock()


@pytest.fixture
def mock_message_sender() -> MagicMock:
    """Mock de MessageSender."""
    sender = MagicMock()
    sender.send_console_msg = AsyncMock()
    return sender


@pytest.mark.asyncio
async def test_handle_send_message_success(
    mock_party_service: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test enviar mensaje a party exitoso."""
    mock_party_service.send_party_message = AsyncMock(return_value=None)

    handler = PartyMessageCommandHandler(
        party_service=mock_party_service,
        message_sender=mock_message_sender,
    )
    command = PartyMessageCommand(user_id=1, message="Hello party!")
    result = await handler.handle(command)

    assert result.success is True
    assert result.data["message"] == "Hello party!"
    assert result.data["error"] is None
    mock_party_service.send_party_message.assert_called_once_with(1, "Hello party!")
    # No debe enviar mensaje de error si result es None
    mock_message_sender.send_console_msg.assert_not_called()


@pytest.mark.asyncio
async def test_handle_send_message_with_error(
    mock_party_service: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test enviar mensaje cuando hay error."""
    mock_party_service.send_party_message = AsyncMock(return_value="No estás en una party")

    handler = PartyMessageCommandHandler(
        party_service=mock_party_service,
        message_sender=mock_message_sender,
    )
    command = PartyMessageCommand(user_id=1, message="Hello party!")
    result = await handler.handle(command)

    assert result.success is True
    assert result.data["error"] == "No estás en una party"
    mock_message_sender.send_console_msg.assert_called_once()


@pytest.mark.asyncio
async def test_handle_invalid_command(
    mock_party_service: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test con comando inválido."""
    handler = PartyMessageCommandHandler(
        party_service=mock_party_service,
        message_sender=mock_message_sender,
    )

    invalid_command = WalkCommand(user_id=1, heading=2)
    result = await handler.handle(invalid_command)

    assert result.success is False


@pytest.mark.asyncio
async def test_handle_error_handling(
    mock_party_service: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test manejo de errores."""
    mock_party_service.send_party_message = AsyncMock(side_effect=Exception("Error"))

    handler = PartyMessageCommandHandler(
        party_service=mock_party_service,
        message_sender=mock_message_sender,
    )
    command = PartyMessageCommand(user_id=1, message="Hello party!")
    result = await handler.handle(command)

    assert result.success is False
    assert "error" in result.error_message.lower()
    mock_message_sender.send_console_msg.assert_called()
