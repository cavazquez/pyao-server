"""Tests para DoubleClickCommandHandler."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.command_handlers.double_click_handler import DoubleClickCommandHandler
from src.commands.base import CommandResult
from src.commands.double_click_command import DoubleClickCommand
from src.commands.walk_command import WalkCommand
from src.models.npc import NPC


@pytest.fixture
def mock_player_repo() -> MagicMock:
    """Mock de PlayerRepository."""
    repo = MagicMock()
    repo.redis = MagicMock()
    return repo


@pytest.fixture
def mock_map_manager() -> MagicMock:
    """Mock de MapManager."""
    return MagicMock()


@pytest.fixture
def mock_message_sender() -> MagicMock:
    """Mock de MessageSender."""
    sender = MagicMock()
    sender.send_console_msg = AsyncMock()
    return sender


@pytest.mark.asyncio
async def test_handle_invalid_command(
    mock_player_repo: MagicMock,
    mock_map_manager: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test con comando inválido."""
    handler = DoubleClickCommandHandler(
        player_repo=mock_player_repo,
        map_manager=mock_map_manager,
        message_sender=mock_message_sender,
    )

    invalid_command = WalkCommand(user_id=1, heading=2)
    result = await handler.handle(invalid_command)

    assert result.success is False
    assert "inválido" in result.error_message.lower()


@pytest.mark.asyncio
async def test_handle_empty_slot(
    mock_player_repo: MagicMock,
    mock_map_manager: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test double click en slot vacío."""
    handler = DoubleClickCommandHandler(
        player_repo=mock_player_repo,
        map_manager=mock_map_manager,
        message_sender=mock_message_sender,
    )

    command = DoubleClickCommand(user_id=1, target=5, map_id=1)
    result = await handler.handle(command)

    # Puede fallar si el slot está vacío o no hay redis
    assert result.success is False


@pytest.mark.asyncio
async def test_handle_npc_click(
    mock_player_repo: MagicMock,
    mock_map_manager: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test double click en NPC (target > MAX_INVENTORY_SLOT)."""
    handler = DoubleClickCommandHandler(
        player_repo=mock_player_repo,
        map_manager=mock_map_manager,
        message_sender=mock_message_sender,
    )

    # Target > 100 es un CharIndex de NPC
    command = DoubleClickCommand(user_id=1, target=10001, map_id=1)
    result = await handler.handle(command)

    # Debe intentar manejar como NPC click
    assert isinstance(result, CommandResult)


@pytest.mark.asyncio
async def test_handle_error_handling(
    mock_player_repo: MagicMock,
    mock_map_manager: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test manejo de errores."""
    mock_map_manager.get_npc_by_char_index = MagicMock(side_effect=Exception("Error"))

    handler = DoubleClickCommandHandler(
        player_repo=mock_player_repo,
        map_manager=mock_map_manager,
        message_sender=mock_message_sender,
    )

    command = DoubleClickCommand(user_id=1, target=10001, map_id=1)
    result = await handler.handle(command)

    # Debe manejar el error
    assert isinstance(result, CommandResult)


@pytest.mark.asyncio
async def test_handle_npc_not_found(
    mock_player_repo: MagicMock,
    mock_map_manager: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test double click en NPC que no existe."""
    mock_map_manager.get_npc_by_char_index = MagicMock(return_value=None)

    handler = DoubleClickCommandHandler(
        player_repo=mock_player_repo,
        map_manager=mock_map_manager,
        message_sender=mock_message_sender,
    )

    command = DoubleClickCommand(user_id=1, target=10001, map_id=1)
    result = await handler.handle(command)

    assert result.success is False
    assert "nadie ahí" in result.error_message.lower()


@pytest.mark.asyncio
async def test_handle_npc_no_map_id(
    mock_player_repo: MagicMock,
    mock_map_manager: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test double click en NPC sin map_id."""
    handler = DoubleClickCommandHandler(
        player_repo=mock_player_repo,
        map_manager=mock_map_manager,
        message_sender=mock_message_sender,
    )

    command = DoubleClickCommand(user_id=1, target=10001, map_id=None)
    result = await handler.handle(command)

    assert result.success is False
    assert "mapa no disponible" in result.error_message.lower()


@pytest.mark.asyncio
async def test_handle_npc_hostile(
    mock_player_repo: MagicMock,
    mock_map_manager: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test double click en NPC hostil."""
    hostile_npc = NPC(
        npc_id=1,
        char_index=10001,
        instance_id="test-123",
        map_id=1,
        x=50,
        y=50,
        heading=3,
        name="Orco",
        description="Un orco hostil",
        body_id=100,
        head_id=0,
        hp=100,
        max_hp=100,
        level=5,
        is_hostile=True,
        is_attackable=True,
    )

    mock_map_manager.get_npc_by_char_index = MagicMock(return_value=hostile_npc)

    handler = DoubleClickCommandHandler(
        player_repo=mock_player_repo,
        map_manager=mock_map_manager,
        message_sender=mock_message_sender,
    )

    command = DoubleClickCommand(user_id=1, target=10001, map_id=1)
    result = await handler.handle(command)

    assert result.success is True
    assert result.data["is_hostile"] is True
    mock_message_sender.send_console_msg.assert_called()


@pytest.mark.asyncio
async def test_handle_npc_friendly(
    mock_player_repo: MagicMock,
    mock_map_manager: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test double click en NPC amigable."""
    friendly_npc = NPC(
        npc_id=2,
        char_index=10002,
        instance_id="test-456",
        map_id=1,
        x=50,
        y=50,
        heading=3,
        name="Aldeano",
        description="Hola, aventurero.",
        body_id=50,
        head_id=10,
        hp=50,
        max_hp=50,
        level=1,
        is_hostile=False,
        is_attackable=False,
    )

    mock_map_manager.get_npc_by_char_index = MagicMock(return_value=friendly_npc)

    handler = DoubleClickCommandHandler(
        player_repo=mock_player_repo,
        map_manager=mock_map_manager,
        message_sender=mock_message_sender,
    )

    command = DoubleClickCommand(user_id=1, target=10002, map_id=1)
    result = await handler.handle(command)

    assert result.success is True
    assert result.data["is_hostile"] is False
    mock_message_sender.send_console_msg.assert_called()
