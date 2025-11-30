"""Tests para SpellInfoCommandHandler."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.command_handlers.spell_info_handler import SpellInfoCommandHandler
from src.commands.spell_info_command import SpellInfoCommand
from src.commands.walk_command import WalkCommand


@pytest.fixture
def mock_spellbook_repo() -> MagicMock:
    """Mock de SpellbookRepository."""
    repo = MagicMock()
    repo.get_spell_in_slot = AsyncMock(return_value=42)
    return repo


@pytest.fixture
def mock_spell_catalog() -> MagicMock:
    """Mock de SpellCatalog."""
    catalog = MagicMock()
    catalog.get_spell_data = MagicMock(
        return_value={
            "name": "Hechizo Test",
            "description": "Descripción del hechizo",
            "min_skill": 50,
            "mana_cost": 30,
            "stamina_cost": 20,
        }
    )
    return catalog


@pytest.fixture
def mock_message_sender() -> MagicMock:
    """Mock de MessageSender."""
    sender = MagicMock()
    sender.send_console_msg = AsyncMock()
    sender.send_multiline_console_msg = AsyncMock()
    return sender


@pytest.mark.asyncio
async def test_handle_valid_spell(
    mock_spellbook_repo: MagicMock,
    mock_spell_catalog: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test información de hechizo válido."""
    handler = SpellInfoCommandHandler(
        spellbook_repo=mock_spellbook_repo,
        spell_catalog=mock_spell_catalog,
        message_sender=mock_message_sender,
    )

    command = SpellInfoCommand(user_id=1, slot=5)
    result = await handler.handle(command)

    assert result.success is True
    mock_message_sender.send_multiline_console_msg.assert_called_once()
    assert result.data["spell_id"] == 42


@pytest.mark.asyncio
async def test_handle_empty_slot(
    mock_spellbook_repo: MagicMock,
    mock_spell_catalog: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test información de hechizo con slot vacío."""
    mock_spellbook_repo.get_spell_in_slot = AsyncMock(return_value=None)

    handler = SpellInfoCommandHandler(
        spellbook_repo=mock_spellbook_repo,
        spell_catalog=mock_spell_catalog,
        message_sender=mock_message_sender,
    )

    command = SpellInfoCommand(user_id=1, slot=5)
    result = await handler.handle(command)

    assert result.success is False
    assert "vacío" in result.error_message.lower()


@pytest.mark.asyncio
async def test_handle_spell_not_found(
    mock_spellbook_repo: MagicMock,
    mock_spell_catalog: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test información de hechizo no encontrado."""
    mock_spell_catalog.get_spell_data = MagicMock(return_value=None)

    handler = SpellInfoCommandHandler(
        spellbook_repo=mock_spellbook_repo,
        spell_catalog=mock_spell_catalog,
        message_sender=mock_message_sender,
    )

    command = SpellInfoCommand(user_id=1, slot=5)
    result = await handler.handle(command)

    assert result.success is False
    assert "no disponibles" in result.error_message.lower()


@pytest.mark.asyncio
async def test_handle_invalid_command(
    mock_spellbook_repo: MagicMock,
    mock_spell_catalog: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test con comando inválido."""
    handler = SpellInfoCommandHandler(
        spellbook_repo=mock_spellbook_repo,
        spell_catalog=mock_spell_catalog,
        message_sender=mock_message_sender,
    )

    invalid_command = WalkCommand(user_id=1, heading=2)
    result = await handler.handle(invalid_command)

    assert result.success is False


@pytest.mark.asyncio
async def test_handle_error_handling(
    mock_spellbook_repo: MagicMock,
    mock_spell_catalog: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test manejo de errores."""
    mock_spellbook_repo.get_spell_in_slot = AsyncMock(side_effect=Exception("Error"))

    handler = SpellInfoCommandHandler(
        spellbook_repo=mock_spellbook_repo,
        spell_catalog=mock_spell_catalog,
        message_sender=mock_message_sender,
    )

    command = SpellInfoCommand(user_id=1, slot=5)
    result = await handler.handle(command)

    assert result.success is False
    assert "error" in result.error_message.lower()
