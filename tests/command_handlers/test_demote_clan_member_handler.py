"""Tests para DemoteClanMemberCommandHandler."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.command_handlers.demote_clan_member_handler import DemoteClanMemberCommandHandler
from src.commands.demote_clan_member_command import DemoteClanMemberCommand
from src.commands.walk_command import WalkCommand


@pytest.fixture
def mock_clan_service() -> MagicMock:
    """Mock de ClanService."""
    return MagicMock()


@pytest.mark.asyncio
async def test_handle_demote_success(mock_clan_service: MagicMock) -> None:
    """Test degradar miembro exitoso."""
    mock_clan_service.demote_member = AsyncMock(return_value=(True, "Miembro degradado"))

    handler = DemoteClanMemberCommandHandler(clan_service=mock_clan_service, user_id=1)
    command = DemoteClanMemberCommand(target_username="TestUser")
    result = await handler.handle(command)

    assert result.success is True
    assert result.data["message"] == "Miembro degradado"
    mock_clan_service.demote_member.assert_called_once_with(
        demoter_id=1,
        target_username="TestUser",
    )


@pytest.mark.asyncio
async def test_handle_demote_failure(mock_clan_service: MagicMock) -> None:
    """Test degradar miembro fallido."""
    mock_clan_service.demote_member = AsyncMock(return_value=(False, "No tienes permiso"))

    handler = DemoteClanMemberCommandHandler(clan_service=mock_clan_service, user_id=1)
    command = DemoteClanMemberCommand(target_username="TestUser")
    result = await handler.handle(command)

    assert result.success is False
    assert "permiso" in result.error_message


@pytest.mark.asyncio
async def test_handle_invalid_command(mock_clan_service: MagicMock) -> None:
    """Test con comando inválido."""
    handler = DemoteClanMemberCommandHandler(clan_service=mock_clan_service, user_id=1)

    invalid_command = WalkCommand(user_id=1, heading=2)
    result = await handler.handle(invalid_command)

    assert result.success is False


@pytest.mark.asyncio
async def test_handle_error_handling(mock_clan_service: MagicMock) -> None:
    """Test manejo de errores."""
    mock_clan_service.demote_member = AsyncMock(side_effect=Exception("Error"))

    handler = DemoteClanMemberCommandHandler(clan_service=mock_clan_service, user_id=1)
    command = DemoteClanMemberCommand(target_username="TestUser")
    result = await handler.handle(command)

    assert result.success is False
    assert "error" in result.error_message.lower()
