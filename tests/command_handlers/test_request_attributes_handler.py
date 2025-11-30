"""Tests para RequestAttributesCommandHandler."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.command_handlers.request_attributes_handler import RequestAttributesCommandHandler
from src.commands.request_attributes_command import RequestAttributesCommand
from src.commands.walk_command import WalkCommand


@pytest.fixture
def mock_player_repo() -> MagicMock:
    """Mock de PlayerRepository."""
    repo = MagicMock()
    repo.get_attributes = AsyncMock(
        return_value={
            "strength": 15,
            "agility": 14,
            "intelligence": 13,
            "charisma": 12,
            "constitution": 16,
        }
    )
    return repo


@pytest.fixture
def mock_message_sender() -> MagicMock:
    """Mock de MessageSender."""
    sender = MagicMock()
    sender.send_attributes = AsyncMock()
    return sender


@pytest.mark.asyncio
async def test_handle_with_dice_attributes(
    mock_message_sender: MagicMock,
) -> None:
    """Test solicitud con atributos desde sesión."""
    handler = RequestAttributesCommandHandler(
        player_repo=None,
        message_sender=mock_message_sender,
    )

    dice_attrs = {
        "strength": 16,
        "agility": 15,
        "intelligence": 14,
        "charisma": 13,
        "constitution": 17,
    }

    command = RequestAttributesCommand(user_id=None, dice_attributes=dice_attrs)
    result = await handler.handle(command)

    assert result.success is True
    mock_message_sender.send_attributes.assert_called_once_with(
        strength=16,
        agility=15,
        intelligence=14,
        charisma=13,
        constitution=17,
    )
    assert result.data["attributes"] == dice_attrs
    assert result.data["from_session"] is True


@pytest.mark.asyncio
async def test_handle_with_user_id(
    mock_player_repo: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test solicitud con user_id desde repositorio."""
    handler = RequestAttributesCommandHandler(
        player_repo=mock_player_repo,
        message_sender=mock_message_sender,
    )

    command = RequestAttributesCommand(user_id=1, dice_attributes=None)
    result = await handler.handle(command)

    assert result.success is True
    mock_player_repo.get_attributes.assert_called_once_with(1)
    mock_message_sender.send_attributes.assert_called_once_with(
        strength=15,
        agility=14,
        intelligence=13,
        charisma=12,
        constitution=16,
    )
    assert result.data["user_id"] == 1
    assert "attributes" in result.data


@pytest.mark.asyncio
async def test_handle_invalid_command(
    mock_player_repo: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test con comando inválido."""
    handler = RequestAttributesCommandHandler(
        player_repo=mock_player_repo,
        message_sender=mock_message_sender,
    )

    # Pasar un comando de otro tipo
    invalid_command = WalkCommand(user_id=1, heading=2)
    result = await handler.handle(invalid_command)

    assert result.success is False
    assert "inválido" in result.error_message.lower()


@pytest.mark.asyncio
async def test_handle_no_user_id_no_dice(
    mock_message_sender: MagicMock,
) -> None:
    """Test solicitud sin user_id ni dice_attributes."""
    handler = RequestAttributesCommandHandler(
        player_repo=None,
        message_sender=mock_message_sender,
    )

    command = RequestAttributesCommand(user_id=None, dice_attributes=None)
    result = await handler.handle(command)

    assert result.success is False
    mock_message_sender.send_attributes.assert_called_once_with(0, 0, 0, 0, 0)


@pytest.mark.asyncio
async def test_handle_without_player_repo(
    mock_message_sender: MagicMock,
) -> None:
    """Test solicitud sin PlayerRepository."""
    handler = RequestAttributesCommandHandler(
        player_repo=None,
        message_sender=mock_message_sender,
    )

    command = RequestAttributesCommand(user_id=1, dice_attributes=None)
    result = await handler.handle(command)

    assert result.success is False
    assert "no disponible" in result.error_message.lower()
    mock_message_sender.send_attributes.assert_called_once_with(0, 0, 0, 0, 0)


@pytest.mark.asyncio
async def test_handle_attributes_not_found(
    mock_player_repo: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test cuando no se encuentran atributos."""
    mock_player_repo.get_attributes = AsyncMock(return_value=None)

    handler = RequestAttributesCommandHandler(
        player_repo=mock_player_repo,
        message_sender=mock_message_sender,
    )

    command = RequestAttributesCommand(user_id=1, dice_attributes=None)
    result = await handler.handle(command)

    assert result.success is False
    assert "no se encontraron" in result.error_message.lower()
    mock_message_sender.send_attributes.assert_called_once_with(0, 0, 0, 0, 0)


@pytest.mark.asyncio
async def test_handle_error_handling(
    mock_player_repo: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test manejo de errores."""
    mock_player_repo.get_attributes = AsyncMock(side_effect=Exception("Error"))

    handler = RequestAttributesCommandHandler(
        player_repo=mock_player_repo,
        message_sender=mock_message_sender,
    )

    command = RequestAttributesCommand(user_id=1, dice_attributes=None)
    result = await handler.handle(command)

    assert result.success is False
    assert "error" in result.error_message.lower()
    mock_message_sender.send_attributes.assert_called_once_with(0, 0, 0, 0, 0)
