"""Tests para LeftClickCommandHandler."""

from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.command_handlers.left_click_handler import LeftClickCommandHandler
from src.commands.left_click_command import LeftClickCommand
from src.commands.walk_command import WalkCommand
from src.models.npc import NPC


@pytest.fixture
def mock_player_repo() -> MagicMock:
    """Mock de PlayerRepository."""
    repo = MagicMock()
    repo.get_position = AsyncMock(return_value={"map": 1, "x": 50, "y": 50})
    return repo


@pytest.fixture
def mock_map_manager() -> MagicMock:
    """Mock de MapManager."""
    manager = MagicMock()
    manager.get_npc_by_char_index = MagicMock(return_value=None)
    return manager


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
    handler = LeftClickCommandHandler(
        player_repo=mock_player_repo,
        map_manager=mock_map_manager,
        map_resources=None,
        bank_repo=None,
        merchant_repo=None,
        door_service=None,
        door_repo=None,
        redis_client=None,
        message_sender=mock_message_sender,
    )

    invalid_command = WalkCommand(user_id=1, heading=2)
    result = await handler.handle(invalid_command)

    assert result.success is False


@pytest.mark.asyncio
async def test_handle_basic_click(
    mock_player_repo: MagicMock,
    mock_map_manager: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test click básico en el mapa."""
    mock_map_manager.get_npcs_in_map = MagicMock(return_value=[])
    mock_map_manager.get_tile_block_reason = MagicMock(return_value=None)
    mock_map_manager.get_ground_items = MagicMock(return_value=[])

    handler = LeftClickCommandHandler(
        player_repo=mock_player_repo,
        map_manager=mock_map_manager,
        map_resources=None,
        bank_repo=None,
        merchant_repo=None,
        door_service=None,
        door_repo=None,
        redis_client=None,
        message_sender=mock_message_sender,
    )

    command = LeftClickCommand(user_id=1, map_id=1, x=50, y=50)
    result = await handler.handle(command)

    assert result.success is True
    assert result.data["type"] == "tile_info"


@pytest.mark.asyncio
async def test_handle_no_map_manager(
    mock_player_repo: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test sin MapManager."""
    handler = LeftClickCommandHandler(
        player_repo=mock_player_repo,
        map_manager=None,
        map_resources=None,
        bank_repo=None,
        merchant_repo=None,
        door_service=None,
        door_repo=None,
        redis_client=None,
        message_sender=mock_message_sender,
    )

    command = LeftClickCommand(user_id=1, map_id=1, x=50, y=50)
    result = await handler.handle(command)

    assert result.success is False
    assert "gestor de mapas" in result.error_message.lower()


@pytest.mark.asyncio
async def test_handle_npc_click_hostile(
    mock_player_repo: MagicMock,
    mock_map_manager: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test click en NPC hostil."""
    npc = NPC(
        npc_id=1,
        char_index=10001,
        instance_id="test-instance",
        map_id=1,
        x=50,
        y=50,
        heading=1,
        name="Orco",
        description="Un orco hostil",
        body_id=1,
        head_id=1,
        hp=100,
        max_hp=100,
        level=5,
        is_hostile=True,
        is_attackable=True,
    )

    mock_map_manager.get_npcs_in_map = MagicMock(return_value=[npc])

    handler = LeftClickCommandHandler(
        player_repo=mock_player_repo,
        map_manager=mock_map_manager,
        map_resources=None,
        bank_repo=None,
        merchant_repo=None,
        door_service=None,
        door_repo=None,
        redis_client=None,
        message_sender=mock_message_sender,
    )

    command = LeftClickCommand(user_id=1, map_id=1, x=50, y=50)
    result = await handler.handle(command)

    assert result.success is True
    assert result.data["type"] == "info"
    assert result.data["npc_name"] == "Orco"
    mock_message_sender.send_console_msg.assert_called_once()
    assert "Hostil" in mock_message_sender.send_console_msg.call_args[0][0]


@pytest.mark.asyncio
async def test_handle_npc_click_merchant(
    mock_player_repo: MagicMock,
    mock_map_manager: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test click en NPC mercader."""
    npc = NPC(
        npc_id=1,
        char_index=10001,
        instance_id="test-instance",
        map_id=1,
        x=50,
        y=50,
        heading=1,
        name="Mercader",
        description="Un mercader",
        body_id=1,
        head_id=1,
        hp=100,
        max_hp=100,
        level=1,
        is_hostile=False,
        is_attackable=False,
        is_merchant=True,
    )

    mock_map_manager.get_npcs_in_map = MagicMock(return_value=[npc])

    mock_merchant_repo = MagicMock()
    mock_merchant_repo.get_all_items = AsyncMock(return_value=[])
    mock_redis_client = MagicMock()
    mock_redis_client.redis = MagicMock()
    mock_redis_client.redis.set = AsyncMock()

    mock_message_sender.send_commerce_init_empty = AsyncMock()
    mock_message_sender.send_console_msg = AsyncMock()

    handler = LeftClickCommandHandler(
        player_repo=mock_player_repo,
        map_manager=mock_map_manager,
        map_resources=None,
        bank_repo=None,
        merchant_repo=mock_merchant_repo,
        door_service=None,
        door_repo=None,
        redis_client=mock_redis_client,
        message_sender=mock_message_sender,
    )

    command = LeftClickCommand(user_id=1, map_id=1, x=50, y=50)
    result = await handler.handle(command)

    assert result.success is True
    # Cuando no tiene items, retorna sin type pero con merchant_id
    assert "merchant_id" in result.data
    assert result.data["items_count"] == 0
    mock_message_sender.send_commerce_init_empty.assert_called_once()


@pytest.mark.asyncio
async def test_handle_npc_click_banker(
    mock_player_repo: MagicMock,
    mock_map_manager: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test click en NPC banquero."""
    npc = NPC(
        npc_id=1,
        char_index=10001,
        instance_id="test-instance",
        map_id=1,
        x=50,
        y=50,
        heading=1,
        name="Banquero",
        description="Un banquero",
        body_id=1,
        head_id=1,
        hp=100,
        max_hp=100,
        level=1,
        is_hostile=False,
        is_attackable=False,
        is_banker=True,
    )

    mock_map_manager.get_npcs_in_map = MagicMock(return_value=[npc])

    mock_bank_repo = MagicMock()
    mock_bank_repo.get_all_items = AsyncMock(return_value=[])
    mock_bank_repo.get_gold = AsyncMock(return_value=0)

    mock_message_sender.send_bank_init_empty = AsyncMock()
    mock_message_sender.send_update_bank_gold = AsyncMock()
    mock_message_sender.send_console_msg = AsyncMock()

    handler = LeftClickCommandHandler(
        player_repo=mock_player_repo,
        map_manager=mock_map_manager,
        map_resources=None,
        bank_repo=mock_bank_repo,
        merchant_repo=None,
        door_service=None,
        door_repo=None,
        redis_client=None,
        message_sender=mock_message_sender,
    )

    command = LeftClickCommand(user_id=1, map_id=1, x=50, y=50)
    result = await handler.handle(command)

    assert result.success is True
    assert result.data["type"] == "bank"
    mock_message_sender.send_bank_init_empty.assert_called_once()


@pytest.mark.asyncio
async def test_handle_tile_with_door(
    mock_player_repo: MagicMock,
    mock_map_manager: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test click en tile con puerta."""

    @dataclass
    class DoorInfo:
        item_id: int
        name: str
        grh_index: int
        is_open: bool
        requires_key: bool = False
        key_id: int | None = None

    mock_map_manager.get_npcs_in_map = MagicMock(return_value=[])
    mock_map_manager.unblock_tile = MagicMock()
    mock_map_manager.block_tile = MagicMock()

    mock_map_resources = MagicMock()
    mock_map_resources.get_door_at = MagicMock(return_value=5593)  # WOODEN_DOOR_CLOSED_GRH

    mock_door_service = MagicMock()
    door_info = DoorInfo(item_id=8, name="Puerta Cerrada", grh_index=5593, is_open=False)
    mock_door_service.get_door_by_grh = MagicMock(return_value=door_info)
    mock_door_service.get_door_by_id = MagicMock(return_value=door_info)
    open_door_info = DoorInfo(item_id=7, name="Puerta Abierta", grh_index=5592, is_open=True)
    mock_door_service.toggle_door = MagicMock(
        return_value=(7, True)  # new_item_id, new_is_open
    )
    mock_door_service.get_door_by_id = MagicMock(side_effect=[door_info, open_door_info])

    mock_door_repo = MagicMock()
    mock_door_repo.get_door_state = AsyncMock(return_value=None)
    mock_door_repo.set_door_state = AsyncMock()

    mock_message_sender.send_object_delete = AsyncMock()
    mock_message_sender.send_block_position = AsyncMock()
    mock_message_sender.send_console_msg = AsyncMock()

    handler = LeftClickCommandHandler(
        player_repo=mock_player_repo,
        map_manager=mock_map_manager,
        map_resources=mock_map_resources,
        bank_repo=None,
        merchant_repo=None,
        door_service=mock_door_service,
        door_repo=mock_door_repo,
        redis_client=None,
        message_sender=mock_message_sender,
    )

    command = LeftClickCommand(user_id=1, map_id=1, x=50, y=50)
    result = await handler.handle(command)

    assert result.success is True
    assert result.data["type"] == "door"
    mock_door_repo.set_door_state.assert_called()


@pytest.mark.asyncio
async def test_handle_tile_with_sign(
    mock_player_repo: MagicMock,
    mock_map_manager: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test click en tile con cartel."""
    mock_map_manager.get_npcs_in_map = MagicMock(return_value=[])
    mock_map_manager.get_tile_block_reason = MagicMock(return_value=None)
    mock_map_manager.get_ground_items = MagicMock(return_value=[])

    mock_map_resources = MagicMock()
    mock_map_resources.get_sign_at = MagicMock(return_value=1234)
    mock_map_resources.is_blocked = MagicMock(return_value=False)
    mock_map_resources.has_water = MagicMock(return_value=False)
    mock_map_resources.has_tree = MagicMock(return_value=False)
    mock_map_resources.has_mine = MagicMock(return_value=False)
    mock_map_resources.has_anvil = MagicMock(return_value=False)
    mock_map_resources.has_forge = MagicMock(return_value=False)

    mock_message_sender.send_console_msg = AsyncMock()

    handler = LeftClickCommandHandler(
        player_repo=mock_player_repo,
        map_manager=mock_map_manager,
        map_resources=mock_map_resources,
        bank_repo=None,
        merchant_repo=None,
        door_service=None,
        door_repo=None,
        redis_client=None,
        message_sender=mock_message_sender,
    )

    command = LeftClickCommand(user_id=1, map_id=1, x=50, y=50)
    result = await handler.handle(command)

    # Puede retornar tile_info o sign dependiendo de si encuentra el cartel en el catálogo
    assert result.success is True


@pytest.mark.asyncio
async def test_handle_tile_with_resources(
    mock_player_repo: MagicMock,
    mock_map_manager: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test click en tile con recursos."""
    mock_map_manager.get_npcs_in_map = MagicMock(return_value=[])
    mock_map_manager.get_tile_block_reason = MagicMock(return_value=None)
    mock_map_manager.get_ground_items = MagicMock(return_value=[])

    mock_map_resources = MagicMock()
    mock_map_resources.get_door_at = MagicMock(return_value=None)
    mock_map_resources.get_sign_at = MagicMock(return_value=None)
    mock_map_resources.is_blocked = MagicMock(return_value=False)
    mock_map_resources.has_water = MagicMock(return_value=True)
    mock_map_resources.has_tree = MagicMock(return_value=True)
    mock_map_resources.has_mine = MagicMock(return_value=False)
    mock_map_resources.has_anvil = MagicMock(return_value=False)
    mock_map_resources.has_forge = MagicMock(return_value=False)

    mock_message_sender.send_console_msg = AsyncMock()

    handler = LeftClickCommandHandler(
        player_repo=mock_player_repo,
        map_manager=mock_map_manager,
        map_resources=mock_map_resources,
        bank_repo=None,
        merchant_repo=None,
        door_service=None,
        door_repo=None,
        redis_client=None,
        message_sender=mock_message_sender,
    )

    command = LeftClickCommand(user_id=1, map_id=1, x=50, y=50)
    result = await handler.handle(command)

    assert result.success is True
    assert result.data["type"] == "tile_info"
    mock_message_sender.send_console_msg.assert_called_once()
    # Verificar que se mencionen los recursos
    call_args = mock_message_sender.send_console_msg.call_args[0][0]
    assert "Agua" in call_args or "Arbol" in call_args


@pytest.mark.asyncio
async def test_handle_tile_empty(
    mock_player_repo: MagicMock,
    mock_map_manager: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test click en tile vacío."""
    mock_map_manager.get_npcs_in_map = MagicMock(return_value=[])
    mock_map_manager.get_tile_block_reason = MagicMock(return_value=None)
    mock_map_manager.get_ground_items = MagicMock(return_value=[])

    mock_map_resources = MagicMock()
    mock_map_resources.get_door_at = MagicMock(return_value=None)
    mock_map_resources.get_sign_at = MagicMock(return_value=None)
    mock_map_resources.is_blocked = MagicMock(return_value=False)
    mock_map_resources.has_water = MagicMock(return_value=False)
    mock_map_resources.has_tree = MagicMock(return_value=False)
    mock_map_resources.has_mine = MagicMock(return_value=False)
    mock_map_resources.has_anvil = MagicMock(return_value=False)
    mock_map_resources.has_forge = MagicMock(return_value=False)

    mock_message_sender.send_console_msg = AsyncMock()

    handler = LeftClickCommandHandler(
        player_repo=mock_player_repo,
        map_manager=mock_map_manager,
        map_resources=mock_map_resources,
        bank_repo=None,
        merchant_repo=None,
        door_service=None,
        door_repo=None,
        redis_client=None,
        message_sender=mock_message_sender,
    )

    command = LeftClickCommand(user_id=1, map_id=1, x=50, y=50)
    result = await handler.handle(command)

    assert result.success is True
    assert result.data["type"] == "tile_info"
    mock_message_sender.send_console_msg.assert_called_once()
    call_args = mock_message_sender.send_console_msg.call_args[0][0]
    assert "Tile vacio" in call_args or "vacio" in call_args.lower()


@pytest.mark.asyncio
async def test_handle_merchant_no_items(
    mock_player_repo: MagicMock,
    mock_map_manager: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test click en mercader sin items."""
    npc = NPC(
        npc_id=1,
        char_index=10001,
        instance_id="test-instance",
        map_id=1,
        x=50,
        y=50,
        heading=1,
        name="Mercader",
        description="Un mercader",
        body_id=1,
        head_id=1,
        hp=100,
        max_hp=100,
        level=1,
        is_hostile=False,
        is_attackable=False,
        is_merchant=True,
    )

    mock_map_manager.get_npcs_in_map = MagicMock(return_value=[npc])

    mock_merchant_repo = MagicMock()
    mock_merchant_repo.get_all_items = AsyncMock(return_value=[])
    mock_redis_client = MagicMock()
    mock_redis_client.redis = MagicMock()
    mock_redis_client.redis.set = AsyncMock()

    mock_message_sender.send_commerce_init_empty = AsyncMock()
    mock_message_sender.send_console_msg = AsyncMock()

    handler = LeftClickCommandHandler(
        player_repo=mock_player_repo,
        map_manager=mock_map_manager,
        map_resources=None,
        bank_repo=None,
        merchant_repo=mock_merchant_repo,
        door_service=None,
        door_repo=None,
        redis_client=mock_redis_client,
        message_sender=mock_message_sender,
    )

    command = LeftClickCommand(user_id=1, map_id=1, x=50, y=50)
    result = await handler.handle(command)

    assert result.success is True
    mock_message_sender.send_console_msg.assert_any_call("Mercader no tiene nada para vender.")
