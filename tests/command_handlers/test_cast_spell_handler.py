"""Tests para CastSpellCommandHandler."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.command_handlers.cast_spell_handler import CastSpellCommandHandler
from src.commands.cast_spell_command import CastSpellCommand


@pytest.fixture
def mock_player_repo() -> MagicMock:
    """Mock de PlayerRepository."""
    repo = MagicMock()
    repo.get_position = AsyncMock(return_value={"x": 50, "y": 50, "map": 1, "heading": 3})
    return repo


@pytest.fixture
def mock_spell_service() -> MagicMock:
    """Mock de SpellService."""
    service = MagicMock()
    service.cast_spell = AsyncMock(return_value=True)
    return service


@pytest.fixture
def mock_spellbook_repo() -> MagicMock:
    """Mock de SpellbookRepository."""
    repo = MagicMock()
    repo.get_spell_in_slot = AsyncMock(return_value=1)  # spell_id = 1
    return repo


@pytest.fixture
def mock_stamina_service() -> MagicMock:
    """Mock de StaminaService."""
    service = MagicMock()
    service.consume_stamina = AsyncMock(return_value=True)
    return service


@pytest.fixture
def mock_message_sender() -> MagicMock:
    """Mock de MessageSender."""
    sender = MagicMock()
    sender.send_console_msg = AsyncMock()
    return sender


@pytest.mark.asyncio
async def test_cast_spell_success_with_coords(
    mock_player_repo: MagicMock,
    mock_spell_service: MagicMock,
    mock_spellbook_repo: MagicMock,
    mock_stamina_service: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test lanzar hechizo exitosamente con coordenadas."""
    handler = CastSpellCommandHandler(
        mock_player_repo,
        mock_spell_service,
        mock_spellbook_repo,
        mock_stamina_service,
        mock_message_sender,
    )
    command = CastSpellCommand(user_id=1, slot=1, target_x=51, target_y=50)

    result = await handler.handle(command)

    assert result.success
    assert result.data["spell_id"] == 1
    assert result.data["target_x"] == 51
    mock_spell_service.cast_spell.assert_called_once()


@pytest.mark.asyncio
async def test_cast_spell_success_no_coords(
    mock_player_repo: MagicMock,
    mock_spell_service: MagicMock,
    mock_spellbook_repo: MagicMock,
    mock_stamina_service: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test lanzar hechizo sin coordenadas (usa heading)."""
    # Heading 3 = Sur, target_y debería incrementarse
    mock_player_repo.get_position = AsyncMock(
        return_value={"x": 50, "y": 50, "map": 1, "heading": 3}
    )

    handler = CastSpellCommandHandler(
        mock_player_repo,
        mock_spell_service,
        mock_spellbook_repo,
        mock_stamina_service,
        mock_message_sender,
    )
    command = CastSpellCommand(user_id=1, slot=1, target_x=None, target_y=None)

    result = await handler.handle(command)

    assert result.success
    # Heading 3 = Sur, target_y = 50 + 1 = 51
    assert result.data["target_y"] == 51


@pytest.mark.asyncio
async def test_cast_spell_invalid_command(
    mock_player_repo: MagicMock,
    mock_spell_service: MagicMock,
    mock_spellbook_repo: MagicMock,
    mock_stamina_service: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test comando inválido."""
    handler = CastSpellCommandHandler(
        mock_player_repo,
        mock_spell_service,
        mock_spellbook_repo,
        mock_stamina_service,
        mock_message_sender,
    )
    # Pasamos un comando incorrecto
    wrong_command = MagicMock()

    result = await handler.handle(wrong_command)

    assert not result.success
    assert "se esperaba CastSpellCommand" in result.error_message


@pytest.mark.asyncio
async def test_cast_spell_no_stamina(
    mock_player_repo: MagicMock,
    mock_spell_service: MagicMock,
    mock_spellbook_repo: MagicMock,
    mock_stamina_service: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test sin stamina suficiente."""
    mock_stamina_service.consume_stamina = AsyncMock(return_value=False)

    handler = CastSpellCommandHandler(
        mock_player_repo,
        mock_spell_service,
        mock_spellbook_repo,
        mock_stamina_service,
        mock_message_sender,
    )
    command = CastSpellCommand(user_id=1, slot=1, target_x=51, target_y=50)

    result = await handler.handle(command)

    assert not result.success
    assert "stamina" in result.error_message.lower()


@pytest.mark.asyncio
async def test_cast_spell_invalid_coords(
    mock_player_repo: MagicMock,
    mock_spell_service: MagicMock,
    mock_spellbook_repo: MagicMock,
    mock_stamina_service: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test coordenadas inválidas."""
    handler = CastSpellCommandHandler(
        mock_player_repo,
        mock_spell_service,
        mock_spellbook_repo,
        mock_stamina_service,
        mock_message_sender,
    )
    command = CastSpellCommand(user_id=1, slot=1, target_x=150, target_y=50)  # x > 100

    result = await handler.handle(command)

    assert not result.success
    assert "Coordenadas inválidas" in result.error_message


@pytest.mark.asyncio
async def test_cast_spell_no_spell_in_slot(
    mock_player_repo: MagicMock,
    mock_spell_service: MagicMock,
    mock_spellbook_repo: MagicMock,
    mock_stamina_service: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test slot vacío."""
    mock_spellbook_repo.get_spell_in_slot = AsyncMock(return_value=None)

    handler = CastSpellCommandHandler(
        mock_player_repo,
        mock_spell_service,
        mock_spellbook_repo,
        mock_stamina_service,
        mock_message_sender,
    )
    command = CastSpellCommand(user_id=1, slot=5, target_x=51, target_y=50)

    result = await handler.handle(command)

    assert not result.success
    assert "No tienes ese hechizo" in result.error_message


@pytest.mark.asyncio
async def test_cast_spell_no_position(
    mock_player_repo: MagicMock,
    mock_spell_service: MagicMock,
    mock_spellbook_repo: MagicMock,
    mock_stamina_service: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test sin posición del jugador."""
    mock_player_repo.get_position = AsyncMock(return_value=None)

    handler = CastSpellCommandHandler(
        mock_player_repo,
        mock_spell_service,
        mock_spellbook_repo,
        mock_stamina_service,
        mock_message_sender,
    )
    command = CastSpellCommand(user_id=1, slot=1, target_x=51, target_y=50)

    result = await handler.handle(command)

    assert not result.success
    assert "Posición no encontrada" in result.error_message


@pytest.mark.asyncio
async def test_cast_spell_out_of_range(
    mock_player_repo: MagicMock,
    mock_spell_service: MagicMock,
    mock_spellbook_repo: MagicMock,
    mock_stamina_service: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test target fuera de rango."""
    # Jugador en (50, 50), target en (70, 50) = distancia 20 > MAX_SPELL_RANGE (10)
    handler = CastSpellCommandHandler(
        mock_player_repo,
        mock_spell_service,
        mock_spellbook_repo,
        mock_stamina_service,
        mock_message_sender,
    )
    command = CastSpellCommand(user_id=1, slot=1, target_x=70, target_y=50)

    result = await handler.handle(command)

    assert not result.success
    assert "demasiado lejos" in result.error_message


@pytest.mark.asyncio
async def test_cast_spell_service_failure(
    mock_player_repo: MagicMock,
    mock_spell_service: MagicMock,
    mock_spellbook_repo: MagicMock,
    mock_stamina_service: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test cuando spell_service falla."""
    mock_spell_service.cast_spell = AsyncMock(return_value=False)

    handler = CastSpellCommandHandler(
        mock_player_repo,
        mock_spell_service,
        mock_spellbook_repo,
        mock_stamina_service,
        mock_message_sender,
    )
    command = CastSpellCommand(user_id=1, slot=1, target_x=51, target_y=50)

    result = await handler.handle(command)

    assert not result.success
    assert "Fallo al lanzar el hechizo" in result.error_message


@pytest.mark.asyncio
async def test_cast_spell_no_dependencies(
    mock_message_sender: MagicMock,
) -> None:
    """Test sin dependencias."""
    handler = CastSpellCommandHandler(
        None,  # type: ignore[arg-type]
        None,  # type: ignore[arg-type]
        None,  # type: ignore[arg-type]
        None,
        mock_message_sender,
    )
    command = CastSpellCommand(user_id=1, slot=1, target_x=51, target_y=50)

    result = await handler.handle(command)

    assert not result.success
    assert "dependencias no disponibles" in result.error_message


@pytest.mark.asyncio
async def test_cast_spell_heading_north(
    mock_player_repo: MagicMock,
    mock_spell_service: MagicMock,
    mock_spellbook_repo: MagicMock,
    mock_stamina_service: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test heading norte (1) - target_y decrece."""
    mock_player_repo.get_position = AsyncMock(
        return_value={"x": 50, "y": 50, "map": 1, "heading": 1}
    )

    handler = CastSpellCommandHandler(
        mock_player_repo,
        mock_spell_service,
        mock_spellbook_repo,
        mock_stamina_service,
        mock_message_sender,
    )
    command = CastSpellCommand(user_id=1, slot=1, target_x=None, target_y=None)

    result = await handler.handle(command)

    assert result.success
    assert result.data["target_y"] == 49  # 50 - 1


@pytest.mark.asyncio
async def test_cast_spell_heading_east(
    mock_player_repo: MagicMock,
    mock_spell_service: MagicMock,
    mock_spellbook_repo: MagicMock,
    mock_stamina_service: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test heading este (2) - target_x crece."""
    mock_player_repo.get_position = AsyncMock(
        return_value={"x": 50, "y": 50, "map": 1, "heading": 2}
    )

    handler = CastSpellCommandHandler(
        mock_player_repo,
        mock_spell_service,
        mock_spellbook_repo,
        mock_stamina_service,
        mock_message_sender,
    )
    command = CastSpellCommand(user_id=1, slot=1, target_x=None, target_y=None)

    result = await handler.handle(command)

    assert result.success
    assert result.data["target_x"] == 51  # 50 + 1


@pytest.mark.asyncio
async def test_cast_spell_heading_west(
    mock_player_repo: MagicMock,
    mock_spell_service: MagicMock,
    mock_spellbook_repo: MagicMock,
    mock_stamina_service: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test heading oeste (4) - target_x decrece."""
    mock_player_repo.get_position = AsyncMock(
        return_value={"x": 50, "y": 50, "map": 1, "heading": 4}
    )

    handler = CastSpellCommandHandler(
        mock_player_repo,
        mock_spell_service,
        mock_spellbook_repo,
        mock_stamina_service,
        mock_message_sender,
    )
    command = CastSpellCommand(user_id=1, slot=1, target_x=None, target_y=None)

    result = await handler.handle(command)

    assert result.success
    assert result.data["target_x"] == 49  # 50 - 1


@pytest.mark.asyncio
async def test_cast_spell_no_stamina_service(
    mock_player_repo: MagicMock,
    mock_spell_service: MagicMock,
    mock_spellbook_repo: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test sin stamina service (debería funcionar igual)."""
    handler = CastSpellCommandHandler(
        mock_player_repo,
        mock_spell_service,
        mock_spellbook_repo,
        None,  # No stamina service
        mock_message_sender,
    )
    command = CastSpellCommand(user_id=1, slot=1, target_x=51, target_y=50)

    result = await handler.handle(command)

    assert result.success
    mock_spell_service.cast_spell.assert_called_once()


@pytest.mark.asyncio
async def test_cast_spell_exception(
    mock_player_repo: MagicMock,
    mock_spell_service: MagicMock,
    mock_spellbook_repo: MagicMock,
    mock_stamina_service: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test excepción durante cast_spell."""
    mock_spell_service.cast_spell = AsyncMock(side_effect=Exception("Database error"))

    handler = CastSpellCommandHandler(
        mock_player_repo,
        mock_spell_service,
        mock_spellbook_repo,
        mock_stamina_service,
        mock_message_sender,
    )
    command = CastSpellCommand(user_id=1, slot=1, target_x=51, target_y=50)

    result = await handler.handle(command)

    assert not result.success
    assert "Error al lanzar hechizo" in result.error_message
