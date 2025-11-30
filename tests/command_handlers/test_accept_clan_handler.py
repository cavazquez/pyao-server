"""Tests para AcceptClanCommandHandler."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.command_handlers.accept_clan_handler import AcceptClanCommandHandler
from src.commands.accept_clan_command import AcceptClanCommand
from src.commands.walk_command import WalkCommand
from src.models.clan import Clan


@pytest.fixture
def mock_clan_service() -> MagicMock:
    """Mock de ClanService."""
    return MagicMock()


@pytest.mark.asyncio
async def test_handle_accept_invitation_success(mock_clan_service: MagicMock) -> None:
    """Test aceptar invitación exitosa."""
    clan = Clan(clan_id=1, name="Test Clan", description="Test")
    mock_clan_service.accept_invitation = AsyncMock(return_value=(clan, None))

    handler = AcceptClanCommandHandler(clan_service=mock_clan_service, user_id=1)
    command = AcceptClanCommand()
    result = await handler.handle(command)

    assert result.success is True
    assert result.data["clan_id"] == 1
    assert result.data["clan_name"] == "Test Clan"


@pytest.mark.asyncio
async def test_handle_accept_invitation_failure(mock_clan_service: MagicMock) -> None:
    """Test aceptar invitación fallida."""
    mock_clan_service.accept_invitation = AsyncMock(return_value=(None, "No hay invitación"))

    handler = AcceptClanCommandHandler(clan_service=mock_clan_service, user_id=1)
    command = AcceptClanCommand()
    result = await handler.handle(command)

    assert result.success is False
    assert "No hay invitación" in result.error_message


@pytest.mark.asyncio
async def test_handle_invalid_command(mock_clan_service: MagicMock) -> None:
    """Test con comando inválido."""
    handler = AcceptClanCommandHandler(clan_service=mock_clan_service, user_id=1)

    invalid_command = WalkCommand(user_id=1, heading=2)
    result = await handler.handle(invalid_command)

    assert result.success is False


@pytest.mark.asyncio
async def test_handle_error_handling(mock_clan_service: MagicMock) -> None:
    """Test manejo de errores."""
    mock_clan_service.accept_invitation = AsyncMock(side_effect=Exception("Error"))

    handler = AcceptClanCommandHandler(clan_service=mock_clan_service, user_id=1)
    command = AcceptClanCommand()
    result = await handler.handle(command)

    assert result.success is False
    assert "error" in result.error_message.lower()
