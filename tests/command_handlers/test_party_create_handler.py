"""Tests para PartyCreateCommandHandler."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.command_handlers.party_create_handler import PartyCreateCommandHandler
from src.commands.party_create_command import PartyCreateCommand
from src.commands.walk_command import WalkCommand
from src.models.party import Party


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
async def test_handle_create_party_success(
    mock_party_service: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test crear party exitoso."""
    party = Party(party_id=1, leader_id=1, leader_username="TestUser")
    mock_party_service.create_party = AsyncMock(return_value=(party, "Party creada"))

    handler = PartyCreateCommandHandler(
        party_service=mock_party_service,
        message_sender=mock_message_sender,
    )
    command = PartyCreateCommand(user_id=1)
    result = await handler.handle(command)

    assert result.success is True
    assert result.data["party_id"] == 1
    mock_message_sender.send_console_msg.assert_called_once()


@pytest.mark.asyncio
async def test_handle_create_party_failure(
    mock_party_service: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test crear party fallido."""
    mock_party_service.create_party = AsyncMock(return_value=(None, "Ya estás en una party"))

    handler = PartyCreateCommandHandler(
        party_service=mock_party_service,
        message_sender=mock_message_sender,
    )
    command = PartyCreateCommand(user_id=1)
    result = await handler.handle(command)

    assert result.success is False
    assert "party" in result.error_message.lower()


@pytest.mark.asyncio
async def test_handle_invalid_command(
    mock_party_service: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test con comando inválido."""
    handler = PartyCreateCommandHandler(
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
    mock_party_service.create_party = AsyncMock(side_effect=Exception("Error"))

    handler = PartyCreateCommandHandler(
        party_service=mock_party_service,
        message_sender=mock_message_sender,
    )
    command = PartyCreateCommand(user_id=1)
    result = await handler.handle(command)

    assert result.success is False
    assert "error" in result.error_message.lower()
    # Verificar que se envió mensaje de error al cliente
    mock_message_sender.send_console_msg.assert_called()
