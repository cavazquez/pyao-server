"""Tests para RejectClanCommandHandler."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.command_handlers.reject_clan_handler import RejectClanCommandHandler
from src.commands.reject_clan_command import RejectClanCommand
from src.commands.walk_command import WalkCommand


@pytest.fixture
def mock_clan_service() -> MagicMock:
    """Mock de ClanService."""
    return MagicMock()


@pytest.mark.asyncio
async def test_handle_reject_success(mock_clan_service: MagicMock) -> None:
    """Test rechazar invitación exitoso."""
    mock_clan_service.reject_invitation = AsyncMock(return_value="Invitación rechazada")

    handler = RejectClanCommandHandler(clan_service=mock_clan_service, user_id=1)
    command = RejectClanCommand()
    result = await handler.handle(command)

    assert result.success is True
    assert result.data["message"] == "Invitación rechazada"
    mock_clan_service.reject_invitation.assert_called_once_with(user_id=1)


@pytest.mark.asyncio
async def test_handle_invalid_command(mock_clan_service: MagicMock) -> None:
    """Test con comando inválido."""
    handler = RejectClanCommandHandler(clan_service=mock_clan_service, user_id=1)

    invalid_command = WalkCommand(user_id=1, heading=2)
    result = await handler.handle(invalid_command)

    assert result.success is False


@pytest.mark.asyncio
async def test_handle_error_handling(mock_clan_service: MagicMock) -> None:
    """Test manejo de errores."""
    mock_clan_service.reject_invitation = AsyncMock(side_effect=Exception("Error"))

    handler = RejectClanCommandHandler(clan_service=mock_clan_service, user_id=1)
    command = RejectClanCommand()
    result = await handler.handle(command)

    assert result.success is False
    assert "error" in result.error_message.lower()
