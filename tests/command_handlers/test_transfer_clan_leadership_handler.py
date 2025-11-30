"""Tests para TransferClanLeadershipCommandHandler."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.command_handlers.transfer_clan_leadership_handler import (
    TransferClanLeadershipCommandHandler,
)
from src.commands.transfer_clan_leadership_command import TransferClanLeadershipCommand
from src.commands.walk_command import WalkCommand


@pytest.fixture
def mock_clan_service() -> MagicMock:
    """Mock de ClanService."""
    return MagicMock()


@pytest.mark.asyncio
async def test_handle_transfer_success(mock_clan_service: MagicMock) -> None:
    """Test transferir liderazgo exitoso."""
    mock_clan_service.transfer_leadership = AsyncMock(return_value=(True, "Liderazgo transferido"))

    handler = TransferClanLeadershipCommandHandler(clan_service=mock_clan_service, user_id=1)
    command = TransferClanLeadershipCommand(new_leader_username="NewLeader")
    result = await handler.handle(command)

    assert result.success is True
    assert result.data["message"] == "Liderazgo transferido"
    mock_clan_service.transfer_leadership.assert_called_once_with(
        leader_id=1,
        new_leader_username="NewLeader",
    )


@pytest.mark.asyncio
async def test_handle_transfer_failure(mock_clan_service: MagicMock) -> None:
    """Test transferir liderazgo fallido."""
    mock_clan_service.transfer_leadership = AsyncMock(return_value=(False, "Usuario no encontrado"))

    handler = TransferClanLeadershipCommandHandler(clan_service=mock_clan_service, user_id=1)
    command = TransferClanLeadershipCommand(new_leader_username="NewLeader")
    result = await handler.handle(command)

    assert result.success is False
    assert "encontrado" in result.error_message


@pytest.mark.asyncio
async def test_handle_invalid_command(mock_clan_service: MagicMock) -> None:
    """Test con comando inválido."""
    handler = TransferClanLeadershipCommandHandler(clan_service=mock_clan_service, user_id=1)

    invalid_command = WalkCommand(user_id=1, heading=2)
    result = await handler.handle(invalid_command)

    assert result.success is False


@pytest.mark.asyncio
async def test_handle_error_handling(mock_clan_service: MagicMock) -> None:
    """Test manejo de errores."""
    mock_clan_service.transfer_leadership = AsyncMock(side_effect=Exception("Error"))

    handler = TransferClanLeadershipCommandHandler(clan_service=mock_clan_service, user_id=1)
    command = TransferClanLeadershipCommand(new_leader_username="NewLeader")
    result = await handler.handle(command)

    assert result.success is False
    assert "error" in result.error_message.lower()
