"""Tests para PartySetLeaderCommandHandler."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.command_handlers.party_set_leader_handler import PartySetLeaderCommandHandler
from src.commands.party_set_leader_command import PartySetLeaderCommand
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
async def test_handle_transfer_leadership_success(
    mock_party_service: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test transferir liderazgo de party exitoso."""
    mock_party_service.transfer_leadership = AsyncMock(return_value="Liderazgo transferido")

    handler = PartySetLeaderCommandHandler(
        party_service=mock_party_service,
        message_sender=mock_message_sender,
    )
    command = PartySetLeaderCommand(user_id=1, target_username="NewLeader")
    result = await handler.handle(command)

    assert result.success is True
    assert result.data["target_username"] == "NewLeader"
    assert result.data["message"] == "Liderazgo transferido"
    mock_party_service.transfer_leadership.assert_called_once_with(1, "NewLeader")
    mock_message_sender.send_console_msg.assert_called_once()


@pytest.mark.asyncio
async def test_handle_invalid_command(
    mock_party_service: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test con comando inválido."""
    handler = PartySetLeaderCommandHandler(
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
    mock_party_service.transfer_leadership = AsyncMock(side_effect=Exception("Error"))

    handler = PartySetLeaderCommandHandler(
        party_service=mock_party_service,
        message_sender=mock_message_sender,
    )
    command = PartySetLeaderCommand(user_id=1, target_username="NewLeader")
    result = await handler.handle(command)

    assert result.success is False
    assert "error" in result.error_message.lower()
    mock_message_sender.send_console_msg.assert_called()
