"""Tests para CommerceSellCommandHandler."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.command_handlers.commerce_sell_handler import CommerceSellCommandHandler
from src.commands.commerce_sell_command import CommerceSellCommand
from src.commands.walk_command import WalkCommand


@pytest.fixture
def mock_commerce_service() -> MagicMock:
    """Mock de CommerceService."""
    service = MagicMock()
    service.sell_item = AsyncMock(return_value=(True, "Venta exitosa"))
    return service


@pytest.fixture
def mock_player_repo() -> MagicMock:
    """Mock de PlayerRepository."""
    repo = MagicMock()
    repo.get_gold = AsyncMock(return_value=1000)
    return repo


@pytest.fixture
def mock_inventory_repo() -> MagicMock:
    """Mock de InventoryRepository."""
    repo = MagicMock()
    repo.MAX_SLOTS = 30
    repo.get_slot = AsyncMock(return_value=None)
    return repo


@pytest.fixture
def mock_redis_client() -> MagicMock:
    """Mock de RedisClient."""
    redis_mock = MagicMock()
    redis_mock.get = AsyncMock(return_value=b"123")  # npc_id

    client = MagicMock()
    client.redis = redis_mock
    return client


@pytest.fixture
def mock_message_sender() -> MagicMock:
    """Mock de MessageSender."""
    sender = MagicMock()
    sender.send_console_msg = AsyncMock()
    sender.send_update_gold = AsyncMock()
    sender.send_change_inventory_slot = AsyncMock()
    return sender


@pytest.mark.asyncio
async def test_handle_sell_success(
    mock_commerce_service: MagicMock,
    mock_player_repo: MagicMock,
    mock_inventory_repo: MagicMock,
    mock_redis_client: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test venta exitosa."""
    handler = CommerceSellCommandHandler(
        commerce_service=mock_commerce_service,
        player_repo=mock_player_repo,
        inventory_repo=mock_inventory_repo,
        redis_client=mock_redis_client,
        message_sender=mock_message_sender,
    )

    command = CommerceSellCommand(user_id=1, slot=1, quantity=1)
    result = await handler.handle(command)

    assert result.success is True
    assert result.data["npc_id"] == 123
    mock_commerce_service.sell_item.assert_called_once_with(1, 123, 1, 1)


@pytest.mark.asyncio
async def test_handle_sell_no_merchant(
    mock_commerce_service: MagicMock,
    mock_player_repo: MagicMock,
    mock_inventory_repo: MagicMock,
    mock_redis_client: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test venta sin mercader activo."""
    mock_redis_client.redis.get = AsyncMock(return_value=None)

    handler = CommerceSellCommandHandler(
        commerce_service=mock_commerce_service,
        player_repo=mock_player_repo,
        inventory_repo=mock_inventory_repo,
        redis_client=mock_redis_client,
        message_sender=mock_message_sender,
    )

    command = CommerceSellCommand(user_id=1, slot=1, quantity=1)
    result = await handler.handle(command)

    assert result.success is False
    assert "comercio" in result.error_message.lower()
    mock_commerce_service.sell_item.assert_not_called()


@pytest.mark.asyncio
async def test_handle_sell_failure(
    mock_commerce_service: MagicMock,
    mock_player_repo: MagicMock,
    mock_inventory_repo: MagicMock,
    mock_redis_client: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test venta fallida."""
    mock_commerce_service.sell_item = AsyncMock(return_value=(False, "Item no encontrado"))

    handler = CommerceSellCommandHandler(
        commerce_service=mock_commerce_service,
        player_repo=mock_player_repo,
        inventory_repo=mock_inventory_repo,
        redis_client=mock_redis_client,
        message_sender=mock_message_sender,
    )

    command = CommerceSellCommand(user_id=1, slot=1, quantity=1)
    result = await handler.handle(command)

    assert result.success is False
    assert "encontrado" in result.error_message


@pytest.mark.asyncio
async def test_handle_invalid_command(
    mock_commerce_service: MagicMock,
    mock_player_repo: MagicMock,
    mock_inventory_repo: MagicMock,
    mock_redis_client: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test con comando inválido."""
    handler = CommerceSellCommandHandler(
        commerce_service=mock_commerce_service,
        player_repo=mock_player_repo,
        inventory_repo=mock_inventory_repo,
        redis_client=mock_redis_client,
        message_sender=mock_message_sender,
    )

    invalid_command = WalkCommand(user_id=1, heading=2)
    result = await handler.handle(invalid_command)

    assert result.success is False
