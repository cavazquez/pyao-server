"""Tests para WalkCommandHandler."""

import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.command_handlers.walk_handler import WalkCommandHandler
from src.commands.use_item_command import UseItemCommand
from src.commands.walk_command import WalkCommand
from src.models.item_constants import BOAT_ITEM_ID


@pytest.fixture
def mock_player_repo() -> MagicMock:
    """Mock de PlayerRepository."""
    repo = MagicMock()
    repo.get_immobilized_until = AsyncMock(return_value=0.0)
    repo.is_meditating = AsyncMock(return_value=False)
    repo.set_meditating = AsyncMock()
    repo.is_sailing = AsyncMock(return_value=False)
    repo.get_position = AsyncMock(return_value={"map": 1, "x": 50, "y": 50, "heading": 3})
    repo.set_position = AsyncMock()
    repo.set_heading = AsyncMock()
    return repo


@pytest.fixture
def mock_map_manager() -> MagicMock:
    """Mock de MapManager."""
    manager = MagicMock()
    manager.can_move_to = MagicMock(return_value=True)
    manager.get_map_size = MagicMock(return_value=(100, 100))
    manager.get_exit_tile = MagicMock(return_value=None)
    manager.get_tile_occupant = MagicMock(return_value=None)
    manager.get_tile_block_reason = MagicMock(return_value=None)
    manager.update_player_tile = MagicMock()
    return manager


@pytest.fixture
def mock_stamina_service() -> MagicMock:
    """Mock de StaminaService."""
    service = MagicMock()
    service.consume_stamina = AsyncMock(return_value=True)
    return service


@pytest.fixture
def mock_broadcast_service() -> MagicMock:
    """Mock de MultiplayerBroadcastService."""
    service = MagicMock()
    service.broadcast_character_move = AsyncMock()
    return service


@pytest.fixture
def mock_player_map_service() -> MagicMock:
    """Mock de PlayerMapService."""
    service = MagicMock()
    service.transition_to_map = AsyncMock()
    return service


@pytest.fixture
def mock_inventory_repo() -> MagicMock:
    """Mock de InventoryRepository."""
    repo = MagicMock()
    repo.get_inventory_slots = AsyncMock(return_value={})
    return repo


@pytest.fixture
def mock_map_resources() -> MagicMock:
    """Mock de MapResourcesService."""
    service = MagicMock()
    service.has_water = MagicMock(return_value=False)
    return service


@pytest.fixture
def mock_message_sender() -> MagicMock:
    """Mock de MessageSender."""
    sender = MagicMock()
    sender.send_console_msg = AsyncMock()
    sender.send_meditate_toggle = AsyncMock()
    sender.console = MagicMock()
    sender.console.send_console_msg = AsyncMock()
    return sender


@pytest.fixture
def walk_handler(
    mock_player_repo: MagicMock,
    mock_map_manager: MagicMock,
    mock_broadcast_service: MagicMock,
    mock_stamina_service: MagicMock,
    mock_player_map_service: MagicMock,
    mock_inventory_repo: MagicMock,
    mock_map_resources: MagicMock,
    mock_message_sender: MagicMock,
) -> WalkCommandHandler:
    """Fixture para crear WalkCommandHandler."""
    return WalkCommandHandler(
        player_repo=mock_player_repo,
        map_manager=mock_map_manager,
        broadcast_service=mock_broadcast_service,
        stamina_service=mock_stamina_service,
        player_map_service=mock_player_map_service,
        inventory_repo=mock_inventory_repo,
        map_resources=mock_map_resources,
        message_sender=mock_message_sender,
    )


@pytest.mark.asyncio
async def test_handle_invalid_command(walk_handler: WalkCommandHandler) -> None:
    """Test con comando inválido."""
    invalid_command = UseItemCommand(user_id=1, slot=5, username="test")
    result = await walk_handler.handle(invalid_command)

    assert result.success is False
    assert "inválido" in result.error_message.lower()


@pytest.mark.asyncio
async def test_handle_no_player_repo(
    mock_map_manager: MagicMock,
    mock_broadcast_service: MagicMock,
    mock_stamina_service: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test sin PlayerRepository."""
    handler = WalkCommandHandler(
        player_repo=None,  # type: ignore[arg-type]
        map_manager=mock_map_manager,
        broadcast_service=mock_broadcast_service,
        stamina_service=mock_stamina_service,
        player_map_service=None,
        inventory_repo=None,
        map_resources=None,
        message_sender=mock_message_sender,
    )

    command = WalkCommand(user_id=1, heading=1)
    result = await handler.handle(command)

    assert result.success is False


@pytest.mark.asyncio
async def test_handle_immobilized_player(
    walk_handler: WalkCommandHandler,
    mock_player_repo: MagicMock,
) -> None:
    """Test con jugador inmovilizado."""
    future_time = time.time() + 10.0
    mock_player_repo.get_immobilized_until = AsyncMock(return_value=future_time)

    command = WalkCommand(user_id=1, heading=1)
    result = await walk_handler.handle(command)

    assert result.success is False
    assert "inmovilizado" in result.error_message.lower()


@pytest.mark.asyncio
async def test_handle_immobilized_expired(
    walk_handler: WalkCommandHandler,
    mock_player_repo: MagicMock,
) -> None:
    """Test con inmovilización expirada."""
    past_time = time.time() - 10.0
    mock_player_repo.get_immobilized_until = AsyncMock(return_value=past_time)

    command = WalkCommand(user_id=1, heading=1)
    result = await walk_handler.handle(command)

    # Debe continuar normalmente
    assert result.success is True


@pytest.mark.asyncio
async def test_handle_no_stamina(
    walk_handler: WalkCommandHandler,
    mock_stamina_service: MagicMock,
) -> None:
    """Test sin stamina suficiente."""
    mock_stamina_service.consume_stamina = AsyncMock(return_value=False)

    command = WalkCommand(user_id=1, heading=1)
    result = await walk_handler.handle(command)

    assert result.success is False
    assert "stamina" in result.error_message.lower()


@pytest.mark.asyncio
async def test_handle_no_position(
    walk_handler: WalkCommandHandler,
    mock_player_repo: MagicMock,
) -> None:
    """Test sin posición encontrada."""
    mock_player_repo.get_position = AsyncMock(return_value=None)

    command = WalkCommand(user_id=1, heading=1)
    result = await walk_handler.handle(command)

    assert result.success is False
    assert "posición" in result.error_message.lower() or "position" in result.error_message.lower()


@pytest.mark.asyncio
async def test_handle_walk_north(walk_handler: WalkCommandHandler) -> None:
    """Test movimiento hacia el norte."""
    command = WalkCommand(user_id=1, heading=1)
    result = await walk_handler.handle(command)

    assert result.success is True
    assert result.data is not None
    assert result.data.get("moved") is True
    assert result.data.get("new_y") == 49


@pytest.mark.asyncio
async def test_handle_walk_east(walk_handler: WalkCommandHandler) -> None:
    """Test movimiento hacia el este."""
    command = WalkCommand(user_id=1, heading=2)
    result = await walk_handler.handle(command)

    assert result.success is True
    assert result.data is not None
    assert result.data.get("moved") is True
    assert result.data.get("new_x") == 51


@pytest.mark.asyncio
async def test_handle_walk_south(walk_handler: WalkCommandHandler) -> None:
    """Test movimiento hacia el sur."""
    command = WalkCommand(user_id=1, heading=3)
    result = await walk_handler.handle(command)

    assert result.success is True
    assert result.data is not None
    assert result.data.get("moved") is True
    assert result.data.get("new_y") == 51


@pytest.mark.asyncio
async def test_handle_walk_west(walk_handler: WalkCommandHandler) -> None:
    """Test movimiento hacia el oeste."""
    command = WalkCommand(user_id=1, heading=4)
    result = await walk_handler.handle(command)

    assert result.success is True
    assert result.data is not None
    assert result.data.get("moved") is True
    assert result.data.get("new_x") == 49


@pytest.mark.asyncio
async def test_handle_map_transition(
    walk_handler: WalkCommandHandler,
    mock_map_manager: MagicMock,
    mock_player_map_service: MagicMock,
) -> None:
    """Test transición de mapa."""
    mock_map_manager.get_exit_tile = MagicMock(return_value={"to_map": 2, "to_x": 10, "to_y": 10})

    command = WalkCommand(user_id=1, heading=1)
    result = await walk_handler.handle(command)

    assert result.success is True
    assert result.data is not None
    assert result.data.get("changed_map") is True
    assert result.data.get("new_map") == 2
    mock_player_map_service.transition_to_map.assert_called_once()


@pytest.mark.asyncio
async def test_handle_map_boundary_no_transition(
    walk_handler: WalkCommandHandler,
    mock_player_repo: MagicMock,
) -> None:
    """Test límite de mapa sin transición."""
    mock_player_repo.get_position = AsyncMock(
        return_value={"map": 1, "x": 50, "y": 1, "heading": 1}
    )

    command = WalkCommand(user_id=1, heading=1)  # Norte, ya en y=1
    result = await walk_handler.handle(command)

    assert result.success is True
    assert result.data is not None
    # No debe moverse porque está en el límite
    assert result.data.get("moved") is False


@pytest.mark.asyncio
async def test_handle_heading_change_no_movement(
    walk_handler: WalkCommandHandler,
    mock_player_repo: MagicMock,
    mock_map_manager: MagicMock,
) -> None:
    """Test cambio de heading sin movimiento."""
    mock_player_repo.get_position = AsyncMock(
        return_value={"map": 1, "x": 50, "y": 1, "heading": 3}
    )
    mock_map_manager.can_move_to = MagicMock(return_value=False)

    command = WalkCommand(user_id=1, heading=1)  # Cambiar a norte
    result = await walk_handler.handle(command)

    assert result.success is True
    mock_player_repo.set_heading.assert_called_once_with(1, 1)


@pytest.mark.asyncio
async def test_handle_blocked_by_water(
    walk_handler: WalkCommandHandler,
    mock_map_resources: MagicMock,
    mock_player_repo: MagicMock,
) -> None:
    """Test bloqueo por agua sin navegación."""
    mock_map_resources.has_water = MagicMock(return_value=True)
    mock_player_repo.is_sailing = AsyncMock(return_value=False)

    command = WalkCommand(user_id=1, heading=1)
    result = await walk_handler.handle(command)

    assert result.success is False
    assert "navegando" in result.error_message.lower() or "navegar" in result.error_message.lower()


@pytest.mark.asyncio
async def test_handle_can_move_on_water_when_sailing(
    walk_handler: WalkCommandHandler,
    mock_map_resources: MagicMock,
    mock_player_repo: MagicMock,
    mock_inventory_repo: MagicMock,
) -> None:
    """Test movimiento sobre agua cuando está navegando."""
    mock_map_resources.has_water = MagicMock(return_value=True)
    mock_player_repo.is_sailing = AsyncMock(return_value=True)

    # Mock de inventario con barca
    mock_slot = MagicMock()
    mock_slot.item_id = BOAT_ITEM_ID
    mock_inventory_repo.get_inventory_slots = AsyncMock(return_value={1: mock_slot})

    command = WalkCommand(user_id=1, heading=1)
    result = await walk_handler.handle(command)

    # Debe permitir el movimiento
    assert result.success is True


@pytest.mark.asyncio
async def test_handle_blocked_by_tile(
    walk_handler: WalkCommandHandler,
    mock_map_manager: MagicMock,
) -> None:
    """Test bloqueo por tile ocupado."""
    mock_map_manager.can_move_to = MagicMock(return_value=False)
    mock_map_manager.get_tile_occupant = MagicMock(return_value="npc_123")

    command = WalkCommand(user_id=1, heading=1)
    result = await walk_handler.handle(command)

    assert result.success is True
    assert result.data is not None
    assert result.data.get("blocked") is True
    assert result.data.get("moved") is False


@pytest.mark.asyncio
async def test_handle_cancel_meditation(
    walk_handler: WalkCommandHandler,
    mock_player_repo: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test cancelar meditación al moverse."""
    mock_player_repo.is_meditating = AsyncMock(return_value=True)

    command = WalkCommand(user_id=1, heading=1)
    await walk_handler.handle(command)

    mock_player_repo.set_meditating.assert_called_once_with(1, is_meditating=False)
    mock_message_sender.send_meditate_toggle.assert_called_once()
    mock_message_sender.send_console_msg.assert_any_call("Dejas de meditar al moverte.")


@pytest.mark.asyncio
async def test_handle_no_map_manager(
    mock_player_repo: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test sin MapManager."""
    handler = WalkCommandHandler(
        player_repo=mock_player_repo,
        map_manager=None,
        broadcast_service=None,
        stamina_service=None,
        player_map_service=None,
        inventory_repo=None,
        map_resources=None,
        message_sender=mock_message_sender,
    )

    command = WalkCommand(user_id=1, heading=1)
    result = await handler.handle(command)

    # Debe funcionar sin MapManager usando límites por defecto
    assert result.success is True


@pytest.mark.asyncio
async def test_handle_no_stamina_service(
    mock_player_repo: MagicMock,
    mock_map_manager: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test sin StaminaService."""
    handler = WalkCommandHandler(
        player_repo=mock_player_repo,
        map_manager=mock_map_manager,
        broadcast_service=None,
        stamina_service=None,
        player_map_service=None,
        inventory_repo=None,
        map_resources=None,
        message_sender=mock_message_sender,
    )

    command = WalkCommand(user_id=1, heading=1)
    result = await handler.handle(command)

    # Debe funcionar sin StaminaService (no consume stamina)
    assert result.success is True


@pytest.mark.asyncio
async def test_handle_broadcast_movement(
    walk_handler: WalkCommandHandler,
    mock_broadcast_service: MagicMock,
) -> None:
    """Test broadcast de movimiento."""
    command = WalkCommand(user_id=1, heading=1)
    await walk_handler.handle(command)

    mock_broadcast_service.broadcast_character_move.assert_called_once()
    call_args = mock_broadcast_service.broadcast_character_move.call_args[1]
    assert call_args["char_index"] == 1
    assert call_args["new_x"] == 50
    assert call_args["new_y"] == 49
    assert call_args["new_heading"] == 1


@pytest.mark.asyncio
async def test_handle_update_position(
    walk_handler: WalkCommandHandler,
    mock_player_repo: MagicMock,
    mock_map_manager: MagicMock,
) -> None:
    """Test actualización de posición."""
    command = WalkCommand(user_id=1, heading=1)
    await walk_handler.handle(command)

    mock_player_repo.set_position.assert_called_once()
    call_args = mock_player_repo.set_position.call_args[0]
    assert call_args[0] == 1  # user_id
    assert call_args[1] == 50  # new_x
    assert call_args[2] == 49  # new_y
    assert call_args[3] == 1  # map
    assert call_args[4] == 1  # heading

    mock_map_manager.update_player_tile.assert_called_once()


@pytest.mark.asyncio
async def test_handle_sail_to_water_tile(
    walk_handler: WalkCommandHandler,
    mock_map_resources: MagicMock,
    mock_player_repo: MagicMock,
    mock_inventory_repo: MagicMock,
) -> None:
    """Test navegar a tile de agua."""
    mock_map_resources.has_water = MagicMock(return_value=True)
    mock_player_repo.is_sailing = AsyncMock(return_value=True)

    mock_slot = MagicMock()
    mock_slot.item_id = BOAT_ITEM_ID
    mock_inventory_repo.get_inventory_slots = AsyncMock(return_value={1: mock_slot})

    # Simular que can_move_to retorna False pero _can_sail_to retorna True
    walk_handler.movement_handler.map_manager.can_move_to = MagicMock(return_value=False)

    command = WalkCommand(user_id=1, heading=1)
    result = await walk_handler.handle(command)

    # Debe permitir movimiento
    assert result.success is True


@pytest.mark.asyncio
async def test_handle_exit_tile_transition(
    walk_handler: WalkCommandHandler,
    mock_map_manager: MagicMock,
    mock_player_map_service: MagicMock,
) -> None:
    """Test transición por exit tile."""
    exit_tile_data = {"to_map": 5, "to_x": 25, "to_y": 30}
    mock_map_manager.get_exit_tile = MagicMock(return_value=exit_tile_data)

    command = WalkCommand(user_id=1, heading=1)
    result = await walk_handler.handle(command)

    assert result.success is True
    assert result.data is not None
    assert result.data.get("changed_map") is True
    assert result.data.get("new_map") == 5
    assert result.data.get("new_x") == 25
    assert result.data.get("new_y") == 30
    mock_player_map_service.transition_to_map.assert_called_once()


@pytest.mark.asyncio
async def test_handle_blocked_movement_reason(
    walk_handler: WalkCommandHandler,
    mock_map_manager: MagicMock,
) -> None:
    """Test razón de bloqueo de movimiento."""
    mock_map_manager.can_move_to = MagicMock(return_value=False)
    mock_map_manager.get_tile_block_reason = MagicMock(return_value="NPC bloqueando")

    command = WalkCommand(user_id=1, heading=1)
    result = await walk_handler.handle(command)

    assert result.success is True
    assert result.data is not None
    assert result.data.get("blocked") is True
