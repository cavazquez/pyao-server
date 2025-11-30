"""Tests para PickupCommandHandler."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.command_handlers.pickup_handler import PickupCommandHandler
from src.commands.pickup_command import PickupCommand
from src.commands.walk_command import WalkCommand
from src.models.item_constants import GOLD_ITEM_ID


@pytest.fixture
def mock_player_repo() -> MagicMock:
    """Mock de PlayerRepository."""
    repo = MagicMock()
    repo.get_position = AsyncMock(return_value={"map": 1, "x": 50, "y": 50})
    repo.get_stats = AsyncMock(return_value={"gold": 1000})
    repo.update_gold = AsyncMock()
    return repo


@pytest.fixture
def mock_inventory_repo() -> MagicMock:
    """Mock de InventoryRepository."""
    repo = MagicMock()
    repo.add_item = AsyncMock(return_value=[(1, 5)])
    return repo


@pytest.fixture
def mock_map_manager() -> MagicMock:
    """Mock de MapManager."""
    manager = MagicMock()
    manager.get_ground_items = MagicMock(return_value=[])
    manager.remove_ground_item = MagicMock()
    return manager


@pytest.fixture
def mock_broadcast_service() -> MagicMock:
    """Mock de MultiplayerBroadcastService."""
    service = MagicMock()
    service.broadcast_object_delete = AsyncMock()
    return service


@pytest.fixture
def mock_item_catalog() -> MagicMock:
    """Mock de ItemCatalog."""
    catalog = MagicMock()
    catalog.get_item_data = MagicMock(return_value={"Name": "Item Test", "GrhIndex": 100})
    return catalog


@pytest.fixture
def mock_message_sender() -> MagicMock:
    """Mock de MessageSender."""
    sender = MagicMock()
    sender.send_console_msg = AsyncMock()
    sender.send_update_user_stats = AsyncMock()
    sender.send_change_inventory_slot = AsyncMock()
    return sender


@pytest.mark.asyncio
async def test_handle_no_items_on_ground(
    mock_player_repo: MagicMock,
    mock_inventory_repo: MagicMock,
    mock_map_manager: MagicMock,
    mock_broadcast_service: MagicMock,
    mock_item_catalog: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test pickup cuando no hay items en el suelo."""
    mock_map_manager.get_ground_items = MagicMock(return_value=[])

    handler = PickupCommandHandler(
        player_repo=mock_player_repo,
        inventory_repo=mock_inventory_repo,
        map_manager=mock_map_manager,
        broadcast_service=mock_broadcast_service,
        item_catalog=mock_item_catalog,
        party_service=None,
        message_sender=mock_message_sender,
    )

    command = PickupCommand(user_id=1)
    result = await handler.handle(command)

    assert result.success is False
    assert "nada aquí" in result.error_message.lower()


@pytest.mark.asyncio
async def test_handle_pickup_gold(
    mock_player_repo: MagicMock,
    mock_inventory_repo: MagicMock,
    mock_map_manager: MagicMock,
    mock_broadcast_service: MagicMock,
    mock_item_catalog: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test pickup de oro."""
    mock_map_manager.get_ground_items = MagicMock(
        return_value=[{"item_id": GOLD_ITEM_ID, "quantity": 500}]
    )

    handler = PickupCommandHandler(
        player_repo=mock_player_repo,
        inventory_repo=mock_inventory_repo,
        map_manager=mock_map_manager,
        broadcast_service=mock_broadcast_service,
        item_catalog=mock_item_catalog,
        party_service=None,
        message_sender=mock_message_sender,
    )

    command = PickupCommand(user_id=1)
    result = await handler.handle(command)

    assert result.success is True
    assert result.data["item_id"] == GOLD_ITEM_ID
    assert result.data["quantity"] == 500
    mock_player_repo.update_gold.assert_called_once()
    mock_map_manager.remove_ground_item.assert_called_once()


@pytest.mark.asyncio
async def test_handle_pickup_item(
    mock_player_repo: MagicMock,
    mock_inventory_repo: MagicMock,
    mock_map_manager: MagicMock,
    mock_broadcast_service: MagicMock,
    mock_item_catalog: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test pickup de item."""
    mock_map_manager.get_ground_items = MagicMock(return_value=[{"item_id": 100, "quantity": 5}])

    handler = PickupCommandHandler(
        player_repo=mock_player_repo,
        inventory_repo=mock_inventory_repo,
        map_manager=mock_map_manager,
        broadcast_service=mock_broadcast_service,
        item_catalog=mock_item_catalog,
        party_service=None,
        message_sender=mock_message_sender,
    )

    command = PickupCommand(user_id=1)
    result = await handler.handle(command)

    assert result.success is True
    assert result.data["item_id"] == 100
    mock_inventory_repo.add_item.assert_called_once()


@pytest.mark.asyncio
async def test_handle_invalid_command(
    mock_player_repo: MagicMock,
    mock_inventory_repo: MagicMock,
    mock_map_manager: MagicMock,
    mock_broadcast_service: MagicMock,
    mock_item_catalog: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test con comando inválido."""
    handler = PickupCommandHandler(
        player_repo=mock_player_repo,
        inventory_repo=mock_inventory_repo,
        map_manager=mock_map_manager,
        broadcast_service=mock_broadcast_service,
        item_catalog=mock_item_catalog,
        party_service=None,
        message_sender=mock_message_sender,
    )

    invalid_command = WalkCommand(user_id=1, heading=2)
    result = await handler.handle(invalid_command)

    assert result.success is False


@pytest.mark.asyncio
async def test_handle_no_position(
    mock_player_repo: MagicMock,
    mock_inventory_repo: MagicMock,
    mock_map_manager: MagicMock,
    mock_broadcast_service: MagicMock,
    mock_item_catalog: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test pickup sin posición del jugador."""
    mock_player_repo.get_position = AsyncMock(return_value=None)

    handler = PickupCommandHandler(
        player_repo=mock_player_repo,
        inventory_repo=mock_inventory_repo,
        map_manager=mock_map_manager,
        broadcast_service=mock_broadcast_service,
        item_catalog=mock_item_catalog,
        party_service=None,
        message_sender=mock_message_sender,
    )

    command = PickupCommand(user_id=1)
    result = await handler.handle(command)

    assert result.success is False


@pytest.mark.asyncio
async def test_handle_pickup_item_full_inventory(
    mock_player_repo: MagicMock,
    mock_inventory_repo: MagicMock,
    mock_map_manager: MagicMock,
    mock_broadcast_service: MagicMock,
    mock_item_catalog: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test pickup cuando el inventario está lleno."""
    mock_map_manager.get_ground_items = MagicMock(return_value=[{"item_id": 100, "quantity": 5}])
    mock_inventory_repo.add_item = AsyncMock(return_value=[])

    handler = PickupCommandHandler(
        player_repo=mock_player_repo,
        inventory_repo=mock_inventory_repo,
        map_manager=mock_map_manager,
        broadcast_service=mock_broadcast_service,
        item_catalog=mock_item_catalog,
        party_service=None,
        message_sender=mock_message_sender,
    )

    command = PickupCommand(user_id=1)
    result = await handler.handle(command)

    assert result.success is False
    assert "lleno" in result.error_message.lower()


@pytest.mark.asyncio
async def test_handle_pickup_item_without_services(
    mock_player_repo: MagicMock,
    mock_map_manager: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test pickup de item sin servicios necesarios."""
    mock_map_manager.get_ground_items = MagicMock(return_value=[{"item_id": 100, "quantity": 5}])

    handler = PickupCommandHandler(
        player_repo=mock_player_repo,
        inventory_repo=None,  # Sin inventory_repo
        map_manager=mock_map_manager,
        broadcast_service=None,
        item_catalog=None,  # Sin item_catalog
        party_service=None,
        message_sender=mock_message_sender,
    )

    command = PickupCommand(user_id=1)
    result = await handler.handle(command)

    assert result.success is False
    assert "no disponibles" in result.error_message.lower()
