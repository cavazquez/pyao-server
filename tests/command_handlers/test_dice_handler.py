"""Tests para DiceCommandHandler."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.command_handlers.dice_handler import DiceCommandHandler
from src.commands.dice_command import DiceCommand
from src.commands.walk_command import WalkCommand


@pytest.fixture
def mock_message_sender() -> MagicMock:
    """Mock de MessageSender."""
    sender = MagicMock()
    sender.connection = MagicMock()
    sender.connection.address = "127.0.0.1:12345"
    sender.send_dice_roll = AsyncMock()
    return sender


@pytest.mark.asyncio
async def test_handle_valid_dice_roll(mock_message_sender: MagicMock) -> None:
    """Test tirada de dados válida."""
    handler = DiceCommandHandler(message_sender=mock_message_sender)

    command = DiceCommand(min_value=10, max_value=18)
    result = await handler.handle(command)

    assert result.success is True
    assert "attributes" in result.data
    assert all(
        stat in result.data["attributes"]
        for stat in ["strength", "agility", "intelligence", "charisma", "constitution"]
    )
    mock_message_sender.send_dice_roll.assert_called_once()


@pytest.mark.asyncio
async def test_handle_dice_roll_values_in_range(mock_message_sender: MagicMock) -> None:
    """Test que los valores de los dados están en el rango correcto."""
    handler = DiceCommandHandler(message_sender=mock_message_sender)

    command = DiceCommand(min_value=15, max_value=18)
    result = await handler.handle(command)

    assert result.success is True
    attributes = result.data["attributes"]
    for stat_value in attributes.values():
        assert 15 <= stat_value <= 18


@pytest.mark.asyncio
async def test_handle_invalid_command(mock_message_sender: MagicMock) -> None:
    """Test con comando inválido."""
    handler = DiceCommandHandler(message_sender=mock_message_sender)

    invalid_command = WalkCommand(user_id=1, heading=2)
    result = await handler.handle(invalid_command)

    assert result.success is False


@pytest.mark.asyncio
async def test_handle_error_handling(mock_message_sender: MagicMock) -> None:
    """Test manejo de errores."""
    mock_message_sender.send_dice_roll = AsyncMock(side_effect=Exception("Error"))

    handler = DiceCommandHandler(message_sender=mock_message_sender)

    command = DiceCommand(min_value=10, max_value=18)
    result = await handler.handle(command)

    assert result.success is False
    assert "error" in result.error_message.lower()
