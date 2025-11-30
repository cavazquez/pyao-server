"""Tests para CreateClanCommandHandler."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.command_handlers.create_clan_handler import CreateClanCommandHandler
from src.commands.create_clan_command import CreateClanCommand
from src.commands.walk_command import WalkCommand
from src.models.clan import Clan


@pytest.fixture
def mock_clan_service() -> MagicMock:
    """Mock de ClanService."""
    return MagicMock()


@pytest.mark.asyncio
async def test_handle_create_clan_success(mock_clan_service: MagicMock) -> None:
    """Test crear clan exitoso."""
    clan = Clan(clan_id=1, name="Test Clan", description="Test Description")
    mock_clan_service.create_clan = AsyncMock(return_value=(clan, None))

    handler = CreateClanCommandHandler(
        clan_service=mock_clan_service,
        user_id=1,
        username="TestUser",
    )
    command = CreateClanCommand(clan_name="Test Clan", description="Test Description")
    result = await handler.handle(command)

    assert result.success is True
    assert result.data["clan_id"] == 1
    assert result.data["clan_name"] == "Test Clan"
    mock_clan_service.create_clan.assert_called_once_with(
        user_id=1,
        clan_name="Test Clan",
        description="Test Description",
        username="TestUser",
    )


@pytest.mark.asyncio
async def test_handle_create_clan_failure(mock_clan_service: MagicMock) -> None:
    """Test crear clan fallido."""
    mock_clan_service.create_clan = AsyncMock(return_value=(None, "Nombre de clan inválido"))

    handler = CreateClanCommandHandler(
        clan_service=mock_clan_service,
        user_id=1,
        username="TestUser",
    )
    command = CreateClanCommand(clan_name="", description="")
    result = await handler.handle(command)

    assert result.success is False
    assert "inválido" in result.error_message


@pytest.mark.asyncio
async def test_handle_invalid_command(mock_clan_service: MagicMock) -> None:
    """Test con comando inválido."""
    handler = CreateClanCommandHandler(
        clan_service=mock_clan_service,
        user_id=1,
        username="TestUser",
    )

    invalid_command = WalkCommand(user_id=1, heading=2)
    result = await handler.handle(invalid_command)

    assert result.success is False


@pytest.mark.asyncio
async def test_handle_error_handling(mock_clan_service: MagicMock) -> None:
    """Test manejo de errores."""
    mock_clan_service.create_clan = AsyncMock(side_effect=Exception("Error"))

    handler = CreateClanCommandHandler(
        clan_service=mock_clan_service,
        user_id=1,
        username="TestUser",
    )
    command = CreateClanCommand(clan_name="Test Clan", description="Test")
    result = await handler.handle(command)

    assert result.success is False
    assert "error" in result.error_message.lower()
