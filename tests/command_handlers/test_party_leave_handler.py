"""Tests para PartyLeaveCommandHandler."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.command_handlers.party_leave_handler import PartyLeaveCommandHandler
from src.commands.party_leave_command import PartyLeaveCommand
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
async def test_handle_leave_party_success(
    mock_party_service: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test abandonar party exitoso."""
    mock_party_service.leave_party = AsyncMock(return_value="Party abandonada")

    handler = PartyLeaveCommandHandler(
        party_service=mock_party_service,
        message_sender=mock_message_sender,
    )
    command = PartyLeaveCommand(user_id=1)
    result = await handler.handle(command)

    assert result.success is True
    assert result.data["message"] == "Party abandonada"
    mock_message_sender.send_console_msg.assert_called_once()


@pytest.mark.asyncio
async def test_handle_invalid_command(
    mock_party_service: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test con comando inválido."""
    handler = PartyLeaveCommandHandler(
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
    mock_party_service.leave_party = AsyncMock(side_effect=Exception("Error"))

    handler = PartyLeaveCommandHandler(
        party_service=mock_party_service,
        message_sender=mock_message_sender,
    )
    command = PartyLeaveCommand(user_id=1)
    result = await handler.handle(command)

    assert result.success is False
    assert "error" in result.error_message.lower()
    # Verificar que se envió mensaje de error al cliente
    mock_message_sender.send_console_msg.assert_called()
