"""Tests para RequestSkillsCommandHandler."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.command_handlers.request_skills_handler import RequestSkillsCommandHandler
from src.commands.request_skills_command import RequestSkillsCommand
from src.commands.walk_command import WalkCommand


@pytest.fixture
def mock_player_repo() -> MagicMock:
    """Mock de PlayerRepository."""
    repo = MagicMock()
    repo.get_skills = AsyncMock(
        return_value={
            "magia": 10,
            "robustez": 8,
            "agilidad": 12,
            "talar": 5,
            "pesca": 7,
            "mineria": 6,
            "herreria": 9,
            "carpinteria": 4,
            "supervivencia": 11,
        }
    )
    return repo


@pytest.fixture
def mock_message_sender() -> MagicMock:
    """Mock de MessageSender."""
    sender = MagicMock()
    sender.send_update_skills = AsyncMock()
    return sender


@pytest.mark.asyncio
async def test_handle_request_skills_success(
    mock_player_repo: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test solicitud de habilidades exitosa."""
    handler = RequestSkillsCommandHandler(
        player_repo=mock_player_repo,
        message_sender=mock_message_sender,
    )

    command = RequestSkillsCommand(user_id=1)
    result = await handler.handle(command)

    assert result.success is True
    assert "skills" in result.data
    mock_message_sender.send_update_skills.assert_called_once()


@pytest.mark.asyncio
async def test_handle_no_skills_defaults(
    mock_player_repo: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test cuando no hay habilidades, usa valores por defecto."""
    mock_player_repo.get_skills = AsyncMock(return_value=None)

    handler = RequestSkillsCommandHandler(
        player_repo=mock_player_repo,
        message_sender=mock_message_sender,
    )

    command = RequestSkillsCommand(user_id=1)
    result = await handler.handle(command)

    assert result.success is True
    assert "skills" in result.data
    # Verificar que todas las habilidades están en 0 por defecto
    skills = result.data["skills"]
    assert skills["magia"] == 0
    assert skills["robustez"] == 0
    mock_message_sender.send_update_skills.assert_called_once()


@pytest.mark.asyncio
async def test_handle_invalid_command(
    mock_player_repo: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test con comando inválido."""
    handler = RequestSkillsCommandHandler(
        player_repo=mock_player_repo,
        message_sender=mock_message_sender,
    )

    invalid_command = WalkCommand(user_id=1, heading=2)
    result = await handler.handle(invalid_command)

    assert result.success is False


@pytest.mark.asyncio
async def test_handle_error_handling(
    mock_player_repo: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test manejo de errores."""
    mock_player_repo.get_skills = AsyncMock(side_effect=Exception("Error"))

    handler = RequestSkillsCommandHandler(
        player_repo=mock_player_repo,
        message_sender=mock_message_sender,
    )

    command = RequestSkillsCommand(user_id=1)
    result = await handler.handle(command)

    assert result.success is False
    assert "error" in result.error_message.lower()
