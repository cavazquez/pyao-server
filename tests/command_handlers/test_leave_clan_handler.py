"""Tests para LeaveClanCommandHandler."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.command_handlers.leave_clan_handler import LeaveClanCommandHandler
from src.commands.leave_clan_command import LeaveClanCommand
from src.commands.walk_command import WalkCommand


@pytest.fixture
def mock_clan_service() -> MagicMock:
    """Mock de ClanService."""
    return MagicMock()


@pytest.mark.asyncio
async def test_handle_leave_clan_success(mock_clan_service: MagicMock) -> None:
    """Test abandonar clan exitoso."""
    mock_clan_service.leave_clan = AsyncMock(return_value=(True, "Clan abandonado"))

    handler = LeaveClanCommandHandler(clan_service=mock_clan_service, user_id=1)
    command = LeaveClanCommand()
    result = await handler.handle(command)

    assert result.success is True
    assert result.data["message"] == "Clan abandonado"
    mock_clan_service.leave_clan.assert_called_once_with(user_id=1)


@pytest.mark.asyncio
async def test_handle_leave_clan_failure(mock_clan_service: MagicMock) -> None:
    """Test abandonar clan fallido."""
    mock_clan_service.leave_clan = AsyncMock(return_value=(False, "No estás en un clan"))

    handler = LeaveClanCommandHandler(clan_service=mock_clan_service, user_id=1)
    command = LeaveClanCommand()
    result = await handler.handle(command)

    assert result.success is False
    assert "No estás en un clan" in result.error_message


@pytest.mark.asyncio
async def test_handle_invalid_command(mock_clan_service: MagicMock) -> None:
    """Test con comando inválido."""
    handler = LeaveClanCommandHandler(clan_service=mock_clan_service, user_id=1)

    invalid_command = WalkCommand(user_id=1, heading=2)
    result = await handler.handle(invalid_command)

    assert result.success is False


@pytest.mark.asyncio
async def test_handle_error_handling(mock_clan_service: MagicMock) -> None:
    """Test manejo de errores."""
    mock_clan_service.leave_clan = AsyncMock(side_effect=Exception("Error"))

    handler = LeaveClanCommandHandler(clan_service=mock_clan_service, user_id=1)
    command = LeaveClanCommand()
    result = await handler.handle(command)

    assert result.success is False
    assert "error" in result.error_message.lower()
