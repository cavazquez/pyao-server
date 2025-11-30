"""Tests para PromoteClanMemberCommandHandler."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.command_handlers.promote_clan_member_handler import PromoteClanMemberCommandHandler
from src.commands.promote_clan_member_command import PromoteClanMemberCommand
from src.commands.walk_command import WalkCommand


@pytest.fixture
def mock_clan_service() -> MagicMock:
    """Mock de ClanService."""
    return MagicMock()


@pytest.mark.asyncio
async def test_handle_promote_success(mock_clan_service: MagicMock) -> None:
    """Test promover miembro exitoso."""
    mock_clan_service.promote_member = AsyncMock(return_value=(True, "Miembro promovido"))

    handler = PromoteClanMemberCommandHandler(clan_service=mock_clan_service, user_id=1)
    command = PromoteClanMemberCommand(target_username="TestUser")
    result = await handler.handle(command)

    assert result.success is True
    assert result.data["message"] == "Miembro promovido"
    mock_clan_service.promote_member.assert_called_once_with(
        promoter_id=1,
        target_username="TestUser",
    )


@pytest.mark.asyncio
async def test_handle_promote_failure(mock_clan_service: MagicMock) -> None:
    """Test promover miembro fallido."""
    mock_clan_service.promote_member = AsyncMock(return_value=(False, "No tienes permiso"))

    handler = PromoteClanMemberCommandHandler(clan_service=mock_clan_service, user_id=1)
    command = PromoteClanMemberCommand(target_username="TestUser")
    result = await handler.handle(command)

    assert result.success is False
    assert "permiso" in result.error_message


@pytest.mark.asyncio
async def test_handle_invalid_command(mock_clan_service: MagicMock) -> None:
    """Test con comando inválido."""
    handler = PromoteClanMemberCommandHandler(clan_service=mock_clan_service, user_id=1)

    invalid_command = WalkCommand(user_id=1, heading=2)
    result = await handler.handle(invalid_command)

    assert result.success is False


@pytest.mark.asyncio
async def test_handle_error_handling(mock_clan_service: MagicMock) -> None:
    """Test manejo de errores."""
    mock_clan_service.promote_member = AsyncMock(side_effect=Exception("Error"))

    handler = PromoteClanMemberCommandHandler(clan_service=mock_clan_service, user_id=1)
    command = PromoteClanMemberCommand(target_username="TestUser")
    result = await handler.handle(command)

    assert result.success is False
    assert "error" in result.error_message.lower()
