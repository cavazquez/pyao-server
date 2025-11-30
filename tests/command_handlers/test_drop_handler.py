"""Tests para DropCommandHandler."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.command_handlers.drop_handler import DropCommandHandler
from src.commands.drop_command import DropCommand
from src.commands.walk_command import WalkCommand


@pytest.fixture
def mock_player_repo() -> MagicMock:
    """Mock de PlayerRepository."""
    repo = MagicMock()
    repo.get_stats = AsyncMock(return_value={"gold": 1000})
    repo.get_position = AsyncMock(return_value={"map": 1, "x": 50, "y": 50})
    repo.update_gold = AsyncMock()
    return repo


@pytest.fixture
def mock_inventory_repo() -> MagicMock:
    """Mock de InventoryRepository."""
    return MagicMock()


@pytest.fixture
def mock_map_manager() -> MagicMock:
    """Mock de MapManager."""
    manager = MagicMock()
    manager.add_ground_item = MagicMock()
    return manager


@pytest.fixture
def mock_broadcast_service() -> MagicMock:
    """Mock de MultiplayerBroadcastService."""
    service = MagicMock()
    service.broadcast_object_create = AsyncMock()
    return service


@pytest.fixture
def mock_message_sender() -> MagicMock:
    """Mock de MessageSender."""
    sender = MagicMock()
    sender.send_console_msg = AsyncMock()
    sender.send_update_user_stats = AsyncMock()
    return sender


@pytest.mark.asyncio
async def test_handle_drop_gold_success(
    mock_player_repo: MagicMock,
    mock_inventory_repo: MagicMock,
    mock_map_manager: MagicMock,
    mock_broadcast_service: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test drop exitoso de oro."""
    handler = DropCommandHandler(
        player_repo=mock_player_repo,
        inventory_repo=mock_inventory_repo,
        map_manager=mock_map_manager,
        broadcast_service=mock_broadcast_service,
        message_sender=mock_message_sender,
    )

    command = DropCommand(user_id=1, slot=1, quantity=500)
    result = await handler.handle(command)

    assert result.success is True
    mock_player_repo.update_gold.assert_called_once_with(1, 500)
    mock_map_manager.add_ground_item.assert_called_once()
    mock_broadcast_service.broadcast_object_create.assert_called_once()
    assert result.data["quantity"] == 500


@pytest.mark.asyncio
async def test_handle_drop_gold_insufficient(
    mock_player_repo: MagicMock,
    mock_inventory_repo: MagicMock,
    mock_map_manager: MagicMock,
    mock_broadcast_service: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test drop con oro insuficiente."""
    handler = DropCommandHandler(
        player_repo=mock_player_repo,
        inventory_repo=mock_inventory_repo,
        map_manager=mock_map_manager,
        broadcast_service=mock_broadcast_service,
        message_sender=mock_message_sender,
    )

    command = DropCommand(user_id=1, slot=1, quantity=5000)  # Más de lo que tiene
    result = await handler.handle(command)

    # Debe ajustar a lo que tiene (1000)
    assert result.success is True
    mock_player_repo.update_gold.assert_called_once_with(1, 0)
    assert result.data["quantity"] == 1000


@pytest.mark.asyncio
async def test_handle_drop_zero_gold(
    mock_player_repo: MagicMock,
    mock_inventory_repo: MagicMock,
    mock_map_manager: MagicMock,
    mock_broadcast_service: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test drop con cantidad cero."""
    handler = DropCommandHandler(
        player_repo=mock_player_repo,
        inventory_repo=mock_inventory_repo,
        map_manager=mock_map_manager,
        broadcast_service=mock_broadcast_service,
        message_sender=mock_message_sender,
    )

    command = DropCommand(user_id=1, slot=1, quantity=0)
    result = await handler.handle(command)

    assert result.success is False
    assert "inválida" in result.error_message.lower()


@pytest.mark.asyncio
async def test_handle_drop_no_gold(
    mock_player_repo: MagicMock,
    mock_inventory_repo: MagicMock,
    mock_map_manager: MagicMock,
    mock_broadcast_service: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test drop sin oro."""
    mock_player_repo.get_stats = AsyncMock(return_value={"gold": 0})

    handler = DropCommandHandler(
        player_repo=mock_player_repo,
        inventory_repo=mock_inventory_repo,
        map_manager=mock_map_manager,
        broadcast_service=mock_broadcast_service,
        message_sender=mock_message_sender,
    )

    command = DropCommand(user_id=1, slot=1, quantity=100)
    result = await handler.handle(command)

    assert result.success is False
    assert "oro" in result.error_message.lower()


@pytest.mark.asyncio
async def test_handle_invalid_command(
    mock_player_repo: MagicMock,
    mock_inventory_repo: MagicMock,
    mock_map_manager: MagicMock,
    mock_broadcast_service: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test con comando inválido."""
    handler = DropCommandHandler(
        player_repo=mock_player_repo,
        inventory_repo=mock_inventory_repo,
        map_manager=mock_map_manager,
        broadcast_service=mock_broadcast_service,
        message_sender=mock_message_sender,
    )

    # Pasar un comando de otro tipo
    invalid_command = WalkCommand(user_id=1, heading=2)
    result = await handler.handle(invalid_command)

    assert result.success is False
    assert "inválido" in result.error_message.lower()


@pytest.mark.asyncio
async def test_handle_without_position(
    mock_player_repo: MagicMock,
    mock_inventory_repo: MagicMock,
    mock_map_manager: MagicMock,
    mock_broadcast_service: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test drop sin posición del jugador."""
    mock_player_repo.get_position = AsyncMock(return_value=None)

    handler = DropCommandHandler(
        player_repo=mock_player_repo,
        inventory_repo=mock_inventory_repo,
        map_manager=mock_map_manager,
        broadcast_service=mock_broadcast_service,
        message_sender=mock_message_sender,
    )

    command = DropCommand(user_id=1, slot=1, quantity=100)
    result = await handler.handle(command)

    assert result.success is False
    assert "posición" in result.error_message.lower()


@pytest.mark.asyncio
async def test_handle_without_broadcast_service(
    mock_player_repo: MagicMock,
    mock_inventory_repo: MagicMock,
    mock_map_manager: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test drop sin broadcast service."""
    handler = DropCommandHandler(
        player_repo=mock_player_repo,
        inventory_repo=mock_inventory_repo,
        map_manager=mock_map_manager,
        broadcast_service=None,
        message_sender=mock_message_sender,
    )

    command = DropCommand(user_id=1, slot=1, quantity=100)
    result = await handler.handle(command)

    assert result.success is True
    # Debe funcionar sin broadcast service


@pytest.mark.asyncio
async def test_result_data_contains_gold_info(
    mock_player_repo: MagicMock,
    mock_inventory_repo: MagicMock,
    mock_map_manager: MagicMock,
    mock_broadcast_service: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test que el resultado contiene información del oro dropeado."""
    handler = DropCommandHandler(
        player_repo=mock_player_repo,
        inventory_repo=mock_inventory_repo,
        map_manager=mock_map_manager,
        broadcast_service=mock_broadcast_service,
        message_sender=mock_message_sender,
    )

    command = DropCommand(user_id=1, slot=1, quantity=250)
    result = await handler.handle(command)

    assert result.success is True
    assert result.data["item_id"] == 12  # GOLD_ITEM_ID
    assert result.data["quantity"] == 250
    assert result.data["type"] == "gold"
