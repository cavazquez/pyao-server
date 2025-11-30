"""Tests para UseItemCommandHandler."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.command_handlers.use_item_handler import UseItemCommandHandler
from src.commands.use_item_command import UseItemCommand
from src.commands.walk_command import WalkCommand
from src.models.item_constants import BOAT_ITEM_ID
from src.models.item_types import ObjType, TipoPocion


@pytest.fixture
def mock_player_repo() -> MagicMock:
    """Mock de PlayerRepository."""
    repo = MagicMock()
    repo.redis = MagicMock()
    repo.get_stats = AsyncMock(return_value={"min_hp": 50, "max_hp": 100})
    repo.is_working = AsyncMock(return_value=False)
    repo.set_working = AsyncMock()
    repo.is_sailing = AsyncMock(return_value=False)
    repo.set_sailing = AsyncMock()
    repo.get_position = AsyncMock(return_value={"map": 1, "x": 50, "y": 50})
    return repo


@pytest.fixture
def mock_item_catalog() -> MagicMock:
    """Mock de ItemCatalog."""
    return MagicMock()


@pytest.fixture
def mock_message_sender() -> MagicMock:
    """Mock de MessageSender."""
    sender = MagicMock()
    sender.send_console_msg = AsyncMock()
    sender.send_update_user_stats = AsyncMock()
    return sender


@pytest.mark.asyncio
async def test_handle_invalid_command(
    mock_player_repo: MagicMock,
    mock_item_catalog: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test con comando inválido."""
    handler = UseItemCommandHandler(
        player_repo=mock_player_repo,
        map_resources=None,
        account_repo=None,
        message_sender=mock_message_sender,
        item_catalog=mock_item_catalog,
    )

    invalid_command = WalkCommand(user_id=1, heading=2)
    result = await handler.handle(invalid_command)

    assert result.success is False


@pytest.mark.asyncio
async def test_handle_empty_slot(
    mock_player_repo: MagicMock,
    mock_item_catalog: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test usar item con slot vacío."""
    # Mock del inventory_repo que retorna slot vacío
    with patch("src.command_handlers.use_item_handler.InventoryRepository") as mock_inv_repo_class:
        mock_inv_repo = MagicMock()
        mock_inv_repo.get_slot = AsyncMock(return_value=None)
        mock_inv_repo_class.return_value = mock_inv_repo

        handler = UseItemCommandHandler(
            player_repo=mock_player_repo,
            map_resources=None,
            account_repo=None,
            message_sender=mock_message_sender,
            item_catalog=mock_item_catalog,
        )

        command = UseItemCommand(user_id=1, slot=5, username="testuser")
        result = await handler.handle(command)

        assert result.success is False


@pytest.mark.asyncio
async def test_handle_no_player_repo(
    mock_item_catalog: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test usar item sin PlayerRepository."""
    handler = UseItemCommandHandler(
        player_repo=None,  # type: ignore[arg-type]
        map_resources=None,
        account_repo=None,
        message_sender=mock_message_sender,
        item_catalog=mock_item_catalog,
    )

    command = UseItemCommand(user_id=1, slot=5, username="testuser")
    result = await handler.handle(command)

    assert result.success is False


# Tests para herramientas de trabajo
@pytest.mark.asyncio
async def test_handle_work_tool_equipped(
    mock_player_repo: MagicMock,
    mock_item_catalog: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test usar herramienta de trabajo equipada."""
    with (
        patch("src.command_handlers.use_item_handler.InventoryRepository") as mock_inv_repo_class,
        patch("src.command_handlers.use_item_handler.EquipmentRepository") as mock_eq_repo_class,
    ):
        mock_inv_repo = MagicMock()
        mock_inv_repo.get_slot = AsyncMock(return_value=(561, 1))  # Hacha de Leñador
        mock_inv_repo_class.return_value = mock_inv_repo

        mock_eq_repo = MagicMock()
        mock_eq_repo.is_slot_equipped = AsyncMock(return_value=561)
        mock_eq_repo_class.return_value = mock_eq_repo

        mock_message_sender.send_work_request_target = AsyncMock()

        handler = UseItemCommandHandler(
            player_repo=mock_player_repo,
            map_resources=None,
            account_repo=None,
            message_sender=mock_message_sender,
            item_catalog=mock_item_catalog,
        )

        command = UseItemCommand(user_id=1, slot=5, username="testuser")
        result = await handler.handle(command)

        assert result.success is True
        assert result.data["handled"] is True
        assert result.data["skill_type"] == 9
        mock_message_sender.send_work_request_target.assert_called_once_with(9)


@pytest.mark.asyncio
async def test_handle_work_tool_not_equipped(
    mock_player_repo: MagicMock,
    mock_item_catalog: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test usar herramienta de trabajo sin equipar."""
    with (
        patch("src.command_handlers.use_item_handler.InventoryRepository") as mock_inv_repo_class,
        patch("src.command_handlers.use_item_handler.EquipmentRepository") as mock_eq_repo_class,
    ):
        mock_inv_repo = MagicMock()
        mock_inv_repo.get_slot = AsyncMock(return_value=(561, 1))
        mock_inv_repo_class.return_value = mock_inv_repo

        mock_eq_repo = MagicMock()
        mock_eq_repo.is_slot_equipped = AsyncMock(return_value=None)
        mock_eq_repo_class.return_value = mock_eq_repo

        handler = UseItemCommandHandler(
            player_repo=mock_player_repo,
            map_resources=None,
            account_repo=None,
            message_sender=mock_message_sender,
            item_catalog=mock_item_catalog,
        )

        command = UseItemCommand(user_id=1, slot=5, username="testuser")
        result = await handler.handle(command)

        assert result.success is False
        mock_message_sender.send_console_msg.assert_called_with(
            "Debes tener equipada la herramienta para trabajar."
        )


# Tests para barca
@pytest.mark.asyncio
async def test_handle_boat_start_sailing(
    mock_player_repo: MagicMock,
    mock_item_catalog: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test iniciar navegación con barca."""
    with patch("src.command_handlers.use_item_handler.InventoryRepository") as mock_inv_repo_class:
        mock_inv_repo = MagicMock()
        mock_inv_repo.get_slot = AsyncMock(return_value=(BOAT_ITEM_ID, 1))
        mock_inv_repo_class.return_value = mock_inv_repo

        mock_player_repo.is_sailing = AsyncMock(return_value=False)
        mock_player_repo.set_sailing = AsyncMock()
        mock_message_sender.send_console_msg = AsyncMock()
        mock_message_sender.send_navigate_toggle = AsyncMock()
        mock_message_sender.send_character_change = AsyncMock()

        handler = UseItemCommandHandler(
            player_repo=mock_player_repo,
            map_resources=None,
            account_repo=None,
            message_sender=mock_message_sender,
            item_catalog=mock_item_catalog,
        )

        command = UseItemCommand(user_id=1, slot=5, username="testuser")
        result = await handler.handle(command)

        assert result.success is True
        assert result.data["is_sailing"] is True
        mock_player_repo.set_sailing.assert_called_once_with(1, True)  # noqa: FBT003


@pytest.mark.asyncio
async def test_handle_boat_stop_sailing(
    mock_player_repo: MagicMock,
    mock_item_catalog: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test detener navegación con barca."""
    with patch("src.command_handlers.use_item_handler.InventoryRepository") as mock_inv_repo_class:
        mock_inv_repo = MagicMock()
        mock_inv_repo.get_slot = AsyncMock(return_value=(BOAT_ITEM_ID, 1))
        mock_inv_repo_class.return_value = mock_inv_repo

        mock_player_repo.is_sailing = AsyncMock(return_value=True)
        mock_player_repo.set_sailing = AsyncMock()
        mock_message_sender.send_console_msg = AsyncMock()
        mock_message_sender.send_navigate_toggle = AsyncMock()

        handler = UseItemCommandHandler(
            player_repo=mock_player_repo,
            map_resources=None,
            account_repo=None,
            message_sender=mock_message_sender,
            item_catalog=mock_item_catalog,
        )

        command = UseItemCommand(user_id=1, slot=5, username="testuser")
        result = await handler.handle(command)

        assert result.success is True
        assert result.data["is_sailing"] is False
        mock_player_repo.set_sailing.assert_called_once_with(1, False)  # noqa: FBT003


# Tests para manzanas
@pytest.mark.asyncio
async def test_handle_apple_consumption(
    mock_player_repo: MagicMock,
    mock_item_catalog: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test consumir manzana."""
    with patch("src.command_handlers.use_item_handler.InventoryRepository") as mock_inv_repo_class:
        mock_inv_repo = MagicMock()
        mock_inv_repo.get_slot = AsyncMock(return_value=(1, 5))  # 5 manzanas
        mock_inv_repo.remove_item = AsyncMock(return_value=True)
        mock_inv_repo.clear_slot = AsyncMock()
        mock_inv_repo_class.return_value = mock_inv_repo

        mock_player_repo.get_hunger_thirst = AsyncMock(
            return_value={
                "min_hunger": 50,
                "max_hunger": 100,
                "min_water": 80,
                "max_water": 100,
            }
        )
        mock_player_repo.set_hunger_thirst = AsyncMock()
        mock_message_sender.send_update_hunger_and_thirst = AsyncMock()
        mock_message_sender.send_change_inventory_slot = AsyncMock()
        mock_message_sender.send_console_msg = AsyncMock()

        handler = UseItemCommandHandler(
            player_repo=mock_player_repo,
            map_resources=None,
            account_repo=None,
            message_sender=mock_message_sender,
            item_catalog=mock_item_catalog,
        )

        command = UseItemCommand(user_id=1, slot=5, username="testuser")
        result = await handler.handle(command)

        assert result.success is True
        assert result.data["handled"] is True
        mock_inv_repo.remove_item.assert_called_once_with(1, 5, 1)
        mock_message_sender.send_console_msg.assert_any_call("¡Has comido una manzana!")


@pytest.mark.asyncio
async def test_handle_apple_last_one(
    mock_player_repo: MagicMock,
    mock_item_catalog: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test consumir última manzana."""
    with patch("src.command_handlers.use_item_handler.InventoryRepository") as mock_inv_repo_class:
        mock_inv_repo = MagicMock()
        mock_inv_repo.get_slot = AsyncMock(return_value=(1, 1))  # 1 manzana
        mock_inv_repo.clear_slot = AsyncMock()
        mock_inv_repo_class.return_value = mock_inv_repo

        mock_player_repo.get_hunger_thirst = AsyncMock(
            return_value={
                "min_hunger": 50,
                "max_hunger": 100,
                "min_water": 80,
                "max_water": 100,
            }
        )
        mock_player_repo.set_hunger_thirst = AsyncMock()
        mock_message_sender.send_update_hunger_and_thirst = AsyncMock()
        mock_message_sender.send_change_inventory_slot = AsyncMock()

        handler = UseItemCommandHandler(
            player_repo=mock_player_repo,
            map_resources=None,
            account_repo=None,
            message_sender=mock_message_sender,
            item_catalog=mock_item_catalog,
        )

        command = UseItemCommand(user_id=1, slot=5, username="testuser")
        result = await handler.handle(command)

        assert result.success is True
        mock_inv_repo.clear_slot.assert_called_once_with(1, 5)


# Tests para pociones
@pytest.mark.asyncio
async def test_handle_hp_potion(
    mock_player_repo: MagicMock,
    mock_item_catalog: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test consumir poción de HP."""
    with patch("src.command_handlers.use_item_handler.InventoryRepository") as mock_inv_repo_class:
        mock_inv_repo = MagicMock()
        mock_inv_repo.get_slot = AsyncMock(return_value=(38, 3))  # Poción Roja
        mock_inv_repo.remove_item = AsyncMock(return_value=True)
        mock_inv_repo_class.return_value = mock_inv_repo

        mock_item_catalog.get_item_data = MagicMock(
            return_value={
                "ObjType": ObjType.POCIONES,
                "TipoPocion": TipoPocion.HP,
                "MaxModificador": 30,
                "Name": "Poción Roja",
            }
        )

        mock_player_repo.get_stats = AsyncMock(
            return_value={"min_hp": 50, "max_hp": 100, "min_mana": 80, "max_mana": 100}
        )
        mock_player_repo.set_stats = AsyncMock()
        mock_message_sender.send_update_user_stats = AsyncMock()
        mock_message_sender.send_change_inventory_slot = AsyncMock()

        handler = UseItemCommandHandler(
            player_repo=mock_player_repo,
            map_resources=None,
            account_repo=None,
            message_sender=mock_message_sender,
            item_catalog=mock_item_catalog,
        )

        command = UseItemCommand(user_id=1, slot=5, username="testuser")
        result = await handler.handle(command)

        assert result.success is True
        assert result.data["handled"] is True
        mock_player_repo.set_stats.assert_called_once()


@pytest.mark.asyncio
async def test_handle_mana_potion(
    mock_player_repo: MagicMock,
    mock_item_catalog: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test consumir poción de Mana."""
    with patch("src.command_handlers.use_item_handler.InventoryRepository") as mock_inv_repo_class:
        mock_inv_repo = MagicMock()
        mock_inv_repo.get_slot = AsyncMock(return_value=(37, 2))  # Poción Azul
        mock_inv_repo.remove_item = AsyncMock(return_value=True)
        mock_inv_repo_class.return_value = mock_inv_repo

        mock_item_catalog.get_item_data = MagicMock(
            return_value={
                "ObjType": ObjType.POCIONES,
                "TipoPocion": TipoPocion.MANA,
                "MinModificador": 12,
                "MaxModificador": 20,
                "Name": "Poción Azul",
            }
        )

        mock_player_repo.get_stats = AsyncMock(
            return_value={"min_hp": 50, "max_hp": 100, "min_mana": 80, "max_mana": 100}
        )
        mock_player_repo.set_stats = AsyncMock()
        mock_message_sender.send_update_user_stats = AsyncMock()
        mock_message_sender.send_change_inventory_slot = AsyncMock()

        handler = UseItemCommandHandler(
            player_repo=mock_player_repo,
            map_resources=None,
            account_repo=None,
            message_sender=mock_message_sender,
            item_catalog=mock_item_catalog,
        )

        command = UseItemCommand(user_id=1, slot=5, username="testuser")
        result = await handler.handle(command)

        assert result.success is True
        mock_player_repo.set_stats.assert_called_once()


@pytest.mark.asyncio
async def test_handle_agility_potion(
    mock_player_repo: MagicMock,
    mock_item_catalog: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test consumir poción de Agilidad."""
    with patch("src.command_handlers.use_item_handler.InventoryRepository") as mock_inv_repo_class:
        mock_inv_repo = MagicMock()
        mock_inv_repo.get_slot = AsyncMock(return_value=(36, 1))  # Poción Amarilla
        mock_inv_repo.remove_item = AsyncMock(return_value=True)
        mock_inv_repo.clear_slot = AsyncMock()
        mock_inv_repo_class.return_value = mock_inv_repo

        mock_item_catalog.get_item_data = MagicMock(
            return_value={
                "ObjType": ObjType.POCIONES,
                "TipoPocion": TipoPocion.AGILIDAD,
                "MinModificador": 3,
                "MaxModificador": 5,
                "DuracionEfecto": 1000,
                "Name": "Poción Amarilla",
            }
        )

        mock_player_repo.set_agility_modifier = AsyncMock()
        mock_player_repo.get_attributes = AsyncMock(return_value={"strength": 10, "agility": 15})
        mock_message_sender.send_update_strength_and_dexterity = AsyncMock()
        mock_message_sender.send_change_inventory_slot = AsyncMock()

        handler = UseItemCommandHandler(
            player_repo=mock_player_repo,
            map_resources=None,
            account_repo=None,
            message_sender=mock_message_sender,
            item_catalog=mock_item_catalog,
        )

        command = UseItemCommand(user_id=1, slot=5, username="testuser")
        result = await handler.handle(command)

        assert result.success is True
        mock_player_repo.set_agility_modifier.assert_called_once()


@pytest.mark.asyncio
async def test_handle_strength_potion(
    mock_player_repo: MagicMock,
    mock_item_catalog: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test consumir poción de Fuerza."""
    with patch("src.command_handlers.use_item_handler.InventoryRepository") as mock_inv_repo_class:
        mock_inv_repo = MagicMock()
        mock_inv_repo.get_slot = AsyncMock(return_value=(39, 1))  # Poción Verde
        mock_inv_repo.remove_item = AsyncMock(return_value=True)
        mock_inv_repo.clear_slot = AsyncMock()
        mock_inv_repo_class.return_value = mock_inv_repo

        mock_item_catalog.get_item_data = MagicMock(
            return_value={
                "ObjType": ObjType.POCIONES,
                "TipoPocion": TipoPocion.FUERZA,
                "MinModificador": 2,
                "MaxModificador": 6,
                "DuracionEfecto": 1000,
                "Name": "Poción Verde",
            }
        )

        mock_player_repo.set_strength_modifier = AsyncMock()
        mock_player_repo.get_attributes = AsyncMock(return_value={"strength": 10, "agility": 15})
        mock_message_sender.send_update_strength_and_dexterity = AsyncMock()
        mock_message_sender.send_change_inventory_slot = AsyncMock()

        handler = UseItemCommandHandler(
            player_repo=mock_player_repo,
            map_resources=None,
            account_repo=None,
            message_sender=mock_message_sender,
            item_catalog=mock_item_catalog,
        )

        command = UseItemCommand(user_id=1, slot=5, username="testuser")
        result = await handler.handle(command)

        assert result.success is True
        mock_player_repo.set_strength_modifier.assert_called_once()


@pytest.mark.asyncio
async def test_handle_cure_poison_potion(
    mock_player_repo: MagicMock,
    mock_item_catalog: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test consumir poción de cura veneno."""
    with patch("src.command_handlers.use_item_handler.InventoryRepository") as mock_inv_repo_class:
        mock_inv_repo = MagicMock()
        mock_inv_repo.get_slot = AsyncMock(return_value=(166, 1))  # Poción Violeta
        mock_inv_repo.remove_item = AsyncMock(return_value=True)
        mock_inv_repo.clear_slot = AsyncMock()
        mock_inv_repo_class.return_value = mock_inv_repo

        mock_item_catalog.get_item_data = MagicMock(
            return_value={
                "ObjType": ObjType.POCIONES,
                "TipoPocion": TipoPocion.CURA_VENENO,
                "Name": "Poción Violeta",
            }
        )

        mock_player_repo.update_poisoned_until = AsyncMock()
        mock_message_sender.send_console_msg = AsyncMock()
        mock_message_sender.send_change_inventory_slot = AsyncMock()

        handler = UseItemCommandHandler(
            player_repo=mock_player_repo,
            map_resources=None,
            account_repo=None,
            message_sender=mock_message_sender,
            item_catalog=mock_item_catalog,
        )

        command = UseItemCommand(user_id=1, slot=5, username="testuser")
        result = await handler.handle(command)

        assert result.success is True
        mock_player_repo.update_poisoned_until.assert_called_once_with(1, 0.0)
        mock_message_sender.send_console_msg.assert_any_call("Te has curado del envenenamiento.")


@pytest.mark.asyncio
async def test_handle_invisibility_potion(
    mock_player_repo: MagicMock,
    mock_item_catalog: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test consumir poción de invisibilidad."""
    with patch("src.command_handlers.use_item_handler.InventoryRepository") as mock_inv_repo_class:
        mock_inv_repo = MagicMock()
        mock_inv_repo.get_slot = AsyncMock(return_value=(645, 1))  # Poción Negra
        mock_inv_repo.remove_item = AsyncMock(return_value=True)
        mock_inv_repo.clear_slot = AsyncMock()
        mock_inv_repo_class.return_value = mock_inv_repo

        mock_item_catalog.get_item_data = MagicMock(
            return_value={
                "ObjType": ObjType.POCIONES,
                "TipoPocion": TipoPocion.INVISIBLE,
                "Name": "Poción Negra",
            }
        )

        mock_map_manager = MagicMock()
        mock_map_manager.get_all_message_senders_in_map = MagicMock(return_value=[])
        mock_account_repo = MagicMock()
        mock_account_repo.get_account = AsyncMock(return_value=None)

        mock_player_repo.update_invisible_until = AsyncMock()
        mock_player_repo.get_position = AsyncMock(return_value={"map": 1, "x": 50, "y": 50})
        mock_message_sender.send_console_msg = AsyncMock()
        mock_message_sender.send_change_inventory_slot = AsyncMock()

        handler = UseItemCommandHandler(
            player_repo=mock_player_repo,
            map_resources=None,
            account_repo=mock_account_repo,
            message_sender=mock_message_sender,
            item_catalog=mock_item_catalog,
            map_manager=mock_map_manager,
        )

        command = UseItemCommand(user_id=1, slot=5, username="testuser")
        result = await handler.handle(command)

        assert result.success is True
        mock_player_repo.update_invisible_until.assert_called_once()


@pytest.mark.asyncio
async def test_handle_unknown_potion_type(
    mock_player_repo: MagicMock,
    mock_item_catalog: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test consumir poción con tipo desconocido."""
    with patch("src.command_handlers.use_item_handler.InventoryRepository") as mock_inv_repo_class:
        mock_inv_repo = MagicMock()
        mock_inv_repo.get_slot = AsyncMock(return_value=(999, 1))
        mock_inv_repo.remove_item = AsyncMock(return_value=True)
        mock_inv_repo.clear_slot = AsyncMock()
        mock_inv_repo_class.return_value = mock_inv_repo

        mock_item_catalog.get_item_data = MagicMock(
            return_value={
                "ObjType": ObjType.POCIONES,
                "TipoPocion": 99,  # Tipo desconocido
                "Name": "Poción Desconocida",
            }
        )

        mock_message_sender.send_console_msg = AsyncMock()
        mock_message_sender.send_change_inventory_slot = AsyncMock()

        handler = UseItemCommandHandler(
            player_repo=mock_player_repo,
            map_resources=None,
            account_repo=None,
            message_sender=mock_message_sender,
            item_catalog=mock_item_catalog,
        )

        command = UseItemCommand(user_id=1, slot=5, username="testuser")
        result = await handler.handle(command)

        assert result.success is False
        mock_message_sender.send_console_msg.assert_any_call("Esta poción no tiene efecto.")


@pytest.mark.asyncio
async def test_handle_item_no_behavior(
    mock_player_repo: MagicMock,
    mock_item_catalog: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test usar item sin comportamiento definido."""
    with patch("src.command_handlers.use_item_handler.InventoryRepository") as mock_inv_repo_class:
        mock_inv_repo = MagicMock()
        mock_inv_repo.get_slot = AsyncMock(return_value=(9999, 1))
        mock_inv_repo_class.return_value = mock_inv_repo

        mock_item_catalog.get_item_data = MagicMock(return_value=None)

        handler = UseItemCommandHandler(
            player_repo=mock_player_repo,
            map_resources=None,
            account_repo=None,
            message_sender=mock_message_sender,
            item_catalog=mock_item_catalog,
        )

        command = UseItemCommand(user_id=1, slot=5, username="testuser")
        result = await handler.handle(command)

        assert result.success is True
        assert result.data["handled"] is False
