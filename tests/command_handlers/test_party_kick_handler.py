"""Tests para PartyKickCommandHandler."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.command_handlers.party_kick_handler import PartyKickCommandHandler
from src.commands.party_kick_command import PartyKickCommand
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
async def test_handle_kick_member_success(
    mock_party_service: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test expulsar miembro de party exitoso."""
    mock_party_service.kick_member = AsyncMock(return_value="Miembro expulsado")

    handler = PartyKickCommandHandler(
        party_service=mock_party_service,
        message_sender=mock_message_sender,
    )
    command = PartyKickCommand(user_id=1, target_username="TargetUser")
    result = await handler.handle(command)

    assert result.success is True
    assert result.data["target_username"] == "TargetUser"
    assert result.data["message"] == "Miembro expulsado"
    mock_party_service.kick_member.assert_called_once_with(1, "TargetUser")
    mock_message_sender.send_console_msg.assert_called_once()


@pytest.mark.asyncio
async def test_handle_invalid_command(
    mock_party_service: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test con comando inválido."""
    handler = PartyKickCommandHandler(
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
    mock_party_service.kick_member = AsyncMock(side_effect=Exception("Error"))

    handler = PartyKickCommandHandler(
        party_service=mock_party_service,
        message_sender=mock_message_sender,
    )
    command = PartyKickCommand(user_id=1, target_username="TargetUser")
    result = await handler.handle(command)

    assert result.success is False
    assert "error" in result.error_message.lower()
    mock_message_sender.send_console_msg.assert_called()
