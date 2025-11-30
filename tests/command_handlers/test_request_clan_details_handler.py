"""Tests para RequestClanDetailsCommandHandler."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.command_handlers.request_clan_details_handler import RequestClanDetailsCommandHandler
from src.commands.request_clan_details_command import RequestClanDetailsCommand
from src.commands.walk_command import WalkCommand
from src.models.clan import Clan, ClanMember, ClanRank


@pytest.fixture
def mock_clan_service() -> MagicMock:
    """Mock de ClanService."""
    return MagicMock()


@pytest.fixture
def mock_message_sender() -> MagicMock:
    """Mock de MessageSender."""
    sender = MagicMock()
    sender.send_console_msg = AsyncMock()
    return sender


@pytest.fixture
def sample_clan() -> Clan:
    """Clan de ejemplo para tests."""
    clan = Clan(
        clan_id=1,
        name="Test Clan",
        description="Test Description",
        leader_id=1,
        leader_username="LeaderUser",
    )
    # Agregar miembro adicional
    member = ClanMember(user_id=2, username="MemberUser", level=5, rank=ClanRank.MEMBER)
    clan.members[2] = member
    return clan


@pytest.mark.asyncio
async def test_handle_request_clan_details_success(
    mock_clan_service: MagicMock,
    mock_message_sender: MagicMock,
    sample_clan: Clan,
) -> None:
    """Test solicitar detalles de clan exitoso."""
    mock_clan_service.clan_repo = MagicMock()
    mock_clan_service.clan_repo.get_user_clan = AsyncMock(return_value=sample_clan)

    handler = RequestClanDetailsCommandHandler(
        clan_service=mock_clan_service,
        message_sender=mock_message_sender,
        user_id=1,
    )

    command = RequestClanDetailsCommand()
    result = await handler.handle(command)

    assert result.success is True
    # Verificar que se enviaron mensajes al cliente
    assert mock_message_sender.send_console_msg.call_count >= 4


@pytest.mark.asyncio
async def test_handle_no_clan(
    mock_clan_service: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test cuando el usuario no pertenece a ningún clan."""
    mock_clan_service.clan_repo = MagicMock()
    mock_clan_service.clan_repo.get_user_clan = AsyncMock(return_value=None)

    handler = RequestClanDetailsCommandHandler(
        clan_service=mock_clan_service,
        message_sender=mock_message_sender,
        user_id=1,
    )

    command = RequestClanDetailsCommand()
    result = await handler.handle(command)

    assert result.success is False
    assert "clan" in result.error_message.lower()


@pytest.mark.asyncio
async def test_handle_invalid_command(
    mock_clan_service: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test con comando inválido."""
    handler = RequestClanDetailsCommandHandler(
        clan_service=mock_clan_service,
        message_sender=mock_message_sender,
        user_id=1,
    )

    invalid_command = WalkCommand(user_id=1, heading=2)
    result = await handler.handle(invalid_command)

    assert result.success is False


@pytest.mark.asyncio
async def test_handle_error_handling(
    mock_clan_service: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test manejo de errores."""
    mock_clan_service.clan_repo = MagicMock()
    mock_clan_service.clan_repo.get_user_clan = AsyncMock(side_effect=Exception("Error"))

    handler = RequestClanDetailsCommandHandler(
        clan_service=mock_clan_service,
        message_sender=mock_message_sender,
        user_id=1,
    )

    command = RequestClanDetailsCommand()
    result = await handler.handle(command)

    assert result.success is False
    assert "error" in result.error_message.lower()
