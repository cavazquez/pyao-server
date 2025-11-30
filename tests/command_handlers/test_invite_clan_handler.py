"""Tests para InviteClanCommandHandler."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.command_handlers.invite_clan_handler import InviteClanCommandHandler
from src.commands.invite_clan_command import InviteClanCommand
from src.commands.walk_command import WalkCommand


@pytest.fixture
def mock_clan_service() -> MagicMock:
    """Mock de ClanService."""
    return MagicMock()


@pytest.mark.asyncio
async def test_handle_invite_success(mock_clan_service: MagicMock) -> None:
    """Test invitar a clan exitoso."""
    mock_clan_service.invite_to_clan = AsyncMock(return_value="Invitación enviada")

    handler = InviteClanCommandHandler(clan_service=mock_clan_service, user_id=1)
    command = InviteClanCommand(target_username="TestUser")
    result = await handler.handle(command)

    assert result.success is True
    assert result.data["message"] == "Invitación enviada"
    mock_clan_service.invite_to_clan.assert_called_once_with(
        inviter_id=1,
        target_username="TestUser",
    )


@pytest.mark.asyncio
async def test_handle_invalid_command(mock_clan_service: MagicMock) -> None:
    """Test con comando inválido."""
    handler = InviteClanCommandHandler(clan_service=mock_clan_service, user_id=1)

    invalid_command = WalkCommand(user_id=1, heading=2)
    result = await handler.handle(invalid_command)

    assert result.success is False


@pytest.mark.asyncio
async def test_handle_error_handling(mock_clan_service: MagicMock) -> None:
    """Test manejo de errores."""
    mock_clan_service.invite_to_clan = AsyncMock(side_effect=Exception("Error"))

    handler = InviteClanCommandHandler(clan_service=mock_clan_service, user_id=1)
    command = InviteClanCommand(target_username="TestUser")
    result = await handler.handle(command)

    assert result.success is False
    assert "error" in result.error_message.lower()
