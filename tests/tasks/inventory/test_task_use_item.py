"""Tests para TaskUseItem."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.models.item_constants import BOAT_ITEM_ID
from src.tasks.inventory.task_use_item import (
    HEADING_NORTH,
    WORK_TOOL_SKILLS,
    TaskUseItem,
)


@pytest.fixture
def mock_message_sender() -> MagicMock:
    """Crea un mock de MessageSender."""
    sender = MagicMock()
    sender.send_console_msg = AsyncMock()
    sender.send_work_request_target = AsyncMock()
    sender.send_navigate_toggle = AsyncMock()
    sender.send_character_change = AsyncMock()
    sender.send_update_hunger_and_thirst = AsyncMock()
    sender.send_change_inventory_slot = AsyncMock()
    sender.connection.address = "127.0.0.1:1234"
    return sender


@pytest.fixture
def mock_player_repo() -> MagicMock:
    """Crea un mock de PlayerRepository."""
    repo = MagicMock()
    repo.redis = MagicMock()
    repo.get_position = AsyncMock(return_value={"map": 1, "x": 50, "y": 50, "heading": 3})
    repo.is_sailing = AsyncMock(return_value=False)
    repo.set_sailing = AsyncMock()
    repo.get_hunger_thirst = AsyncMock(
        return_value={
            "min_hunger": 50,
            "max_hunger": 100,
            "min_water": 50,
            "max_water": 100,
        }
    )
    repo.set_hunger_thirst = AsyncMock()
    return repo


@pytest.fixture
def mock_map_resources() -> MagicMock:
    """Crea un mock de MapResourcesService."""
    service = MagicMock()
    service.has_water = MagicMock(return_value=False)  # Por defecto no hay agua
    return service


@pytest.fixture
def mock_account_repo() -> MagicMock:
    """Crea un mock de AccountRepository."""
    repo = MagicMock()
    repo.get_account = AsyncMock(
        return_value={"char_race": 1, "char_head": 1}  # Humano, cabeza 1
    )
    return repo


@pytest.mark.asyncio
class TestTaskUseItemExecute:
    """Tests para el método execute de TaskUseItem."""

    async def test_execute_without_session(self, mock_message_sender: MagicMock) -> None:
        """Test sin sesión activa."""
        data = bytes([0x1E, 0x01])  # USE_ITEM + slot=1
        task = TaskUseItem(
            data,
            mock_message_sender,
            slot=1,
            session_data=None,
        )

        await task.execute()

        # No debe hacer nada

    async def test_execute_without_player_repo(self, mock_message_sender: MagicMock) -> None:
        """Test sin PlayerRepository."""
        data = bytes([0x1E, 0x01])
        task = TaskUseItem(
            data,
            mock_message_sender,
            slot=1,
            session_data={"user_id": 1},
            player_repo=None,
        )

        await task.execute()

        # No debe hacer nada

    async def test_execute_empty_slot(
        self, mock_message_sender: MagicMock, mock_player_repo: MagicMock
    ) -> None:
        """Test cuando el slot está vacío."""
        data = bytes([0x1E, 0x01])
        task = TaskUseItem(
            data,
            mock_message_sender,
            slot=1,
            session_data={"user_id": 1},
            player_repo=mock_player_repo,
        )

        with patch("src.tasks.inventory.task_use_item.InventoryRepository") as mock_inv_repo:
            mock_inv_repo_instance = MagicMock()
            mock_inv_repo_instance.get_slot = AsyncMock(return_value=None)  # Slot vacío
            mock_inv_repo.return_value = mock_inv_repo_instance

            await task.execute()

            # No debe hacer nada

    async def test_execute_work_tool(
        self, mock_message_sender: MagicMock, mock_player_repo: MagicMock
    ) -> None:
        """Test usar herramienta de trabajo."""
        data = bytes([0x1E, 0x01])
        # Hacha de Leñador (ID 561) → Skill Talar (9)
        tool_id = 561
        task = TaskUseItem(
            data,
            mock_message_sender,
            slot=1,
            session_data={"user_id": 1},
            player_repo=mock_player_repo,
        )

        with (
            patch("src.tasks.inventory.task_use_item.InventoryRepository") as mock_inv_repo,
            patch("src.tasks.inventory.task_use_item.EquipmentRepository") as mock_equip_repo,
        ):
            mock_inv_repo_instance = MagicMock()
            mock_inv_repo_instance.get_slot = AsyncMock(
                return_value=(tool_id, 1)  # Hacha en slot 1
            )
            mock_inv_repo.return_value = mock_inv_repo_instance

            mock_equip_repo_instance = MagicMock()
            mock_equip_repo_instance.is_slot_equipped = AsyncMock(return_value=True)  # Equipada
            mock_equip_repo.return_value = mock_equip_repo_instance

            await task.execute()

            mock_message_sender.send_work_request_target.assert_called_once_with(
                WORK_TOOL_SKILLS[tool_id]
            )

    async def test_execute_work_tool_not_equipped(
        self, mock_message_sender: MagicMock, mock_player_repo: MagicMock
    ) -> None:
        """Test usar herramienta de trabajo sin equipar."""
        data = bytes([0x1E, 0x01])
        tool_id = 561  # Hacha
        task = TaskUseItem(
            data,
            mock_message_sender,
            slot=1,
            session_data={"user_id": 1},
            player_repo=mock_player_repo,
        )

        with (
            patch("src.tasks.inventory.task_use_item.InventoryRepository") as mock_inv_repo,
            patch("src.tasks.inventory.task_use_item.EquipmentRepository") as mock_equip_repo,
        ):
            mock_inv_repo_instance = MagicMock()
            mock_inv_repo_instance.get_slot = AsyncMock(return_value=(tool_id, 1))
            mock_inv_repo.return_value = mock_inv_repo_instance

            mock_equip_repo_instance = MagicMock()
            mock_equip_repo_instance.is_slot_equipped = AsyncMock(
                return_value=None  # No equipada
            )
            mock_equip_repo.return_value = mock_equip_repo_instance

            await task.execute()

            mock_message_sender.send_console_msg.assert_called_once_with(
                "Debes tener equipada la herramienta para trabajar."
            )
            mock_message_sender.send_work_request_target.assert_not_called()

    async def test_execute_boat(
        self,
        mock_message_sender: MagicMock,
        mock_player_repo: MagicMock,
        mock_map_resources: MagicMock,
        mock_account_repo: MagicMock,
    ) -> None:
        """Test usar barca para entrar en modo navegación."""
        data = bytes([0x1E, 0x01])
        mock_map_resources.has_water = MagicMock(return_value=True)  # Hay agua cerca
        task = TaskUseItem(
            data,
            mock_message_sender,
            slot=1,
            session_data={"user_id": 1, "username": "test"},
            player_repo=mock_player_repo,
            map_resources=mock_map_resources,
            account_repo=mock_account_repo,
        )

        with patch("src.tasks.inventory.task_use_item.InventoryRepository") as mock_inv_repo:
            mock_inv_repo_instance = MagicMock()
            mock_inv_repo_instance.get_slot = AsyncMock(
                return_value=(BOAT_ITEM_ID, 1)  # Barca
            )
            mock_inv_repo.return_value = mock_inv_repo_instance

            await task.execute()

            mock_player_repo.set_sailing.assert_called_once_with(1, True)  # noqa: FBT003
            mock_message_sender.send_console_msg.assert_called_once_with(
                "Has cambiado al modo de navegación"
            )
            mock_message_sender.send_navigate_toggle.assert_called_once()
            mock_message_sender.send_character_change.assert_called_once()

    async def test_execute_apple_consumption(
        self, mock_message_sender: MagicMock, mock_player_repo: MagicMock
    ) -> None:
        """Test consumir manzana."""
        data = bytes([0x1E, 0x01])
        apple_id = 1
        task = TaskUseItem(
            data,
            mock_message_sender,
            slot=1,
            session_data={"user_id": 1},
            player_repo=mock_player_repo,
        )

        with (
            patch("src.tasks.inventory.task_use_item.InventoryRepository") as mock_inv_repo,
            patch("src.tasks.inventory.task_use_item.get_item") as mock_get_item,
        ):
            mock_inv_repo_instance = MagicMock()
            mock_inv_repo_instance.get_slot = AsyncMock(return_value=(apple_id, 5))  # 5 manzanas
            mock_inv_repo_instance.remove_item = AsyncMock(return_value=True)
            mock_inv_repo_instance.clear_slot = AsyncMock()
            mock_inv_repo.return_value = mock_inv_repo_instance

            # Mock del item manzana
            mock_apple = MagicMock()
            mock_apple.name = "Manzana"
            mock_apple.graphic_id = 100
            mock_apple.item_type.to_client_type = MagicMock(return_value=6)
            mock_apple.max_damage = 0
            mock_apple.min_damage = 0
            mock_apple.defense = 0
            mock_apple.value = 10
            mock_get_item.return_value = mock_apple

            await task.execute()

            # Debe remover 1 manzana (quedan 4)
            mock_inv_repo_instance.remove_item.assert_called_once_with(1, 1, 1)
            mock_message_sender.send_console_msg.assert_called_with("¡Has comido una manzana!")
            mock_player_repo.set_hunger_thirst.assert_called_once()

    async def test_execute_apple_last_one(
        self, mock_message_sender: MagicMock, mock_player_repo: MagicMock
    ) -> None:
        """Test consumir última manzana (clear_slot)."""
        data = bytes([0x1E, 0x01])
        apple_id = 1
        task = TaskUseItem(
            data,
            mock_message_sender,
            slot=1,
            session_data={"user_id": 1},
            player_repo=mock_player_repo,
        )

        with (
            patch("src.tasks.inventory.task_use_item.InventoryRepository") as mock_inv_repo,
            patch("src.tasks.inventory.task_use_item.get_item") as mock_get_item,
        ):
            mock_inv_repo_instance = MagicMock()
            mock_inv_repo_instance.get_slot = AsyncMock(return_value=(apple_id, 1))  # 1 manzana
            mock_inv_repo_instance.clear_slot = AsyncMock()
            mock_inv_repo.return_value = mock_inv_repo_instance

            mock_apple = MagicMock()
            mock_apple.name = "Manzana"
            mock_apple.graphic_id = 100
            mock_apple.item_type.to_client_type = MagicMock(return_value=6)
            mock_apple.max_damage = 0
            mock_apple.min_damage = 0
            mock_apple.defense = 0
            mock_apple.value = 10
            mock_get_item.return_value = mock_apple

            await task.execute()

            # Debe limpiar el slot (última manzana)
            mock_inv_repo_instance.clear_slot.assert_called_once_with(1, 1)
            mock_inv_repo_instance.remove_item.assert_not_called()

    async def test_execute_unknown_item(
        self, mock_message_sender: MagicMock, mock_player_repo: MagicMock
    ) -> None:
        """Test usar item sin comportamiento definido."""
        data = bytes([0x1E, 0x01])
        unknown_id = 999
        task = TaskUseItem(
            data,
            mock_message_sender,
            slot=1,
            session_data={"user_id": 1},
            player_repo=mock_player_repo,
        )

        with patch("src.tasks.inventory.task_use_item.InventoryRepository") as mock_inv_repo:
            mock_inv_repo_instance = MagicMock()
            mock_inv_repo_instance.get_slot = AsyncMock(return_value=(unknown_id, 1))
            mock_inv_repo.return_value = mock_inv_repo_instance

            await task.execute()

            # No debe hacer nada, solo loggear


@pytest.mark.asyncio
class TestTaskUseItemBoat:
    """Tests para el manejo de barca/navegación."""

    async def test_boat_cannot_start_sailing_no_water(
        self,
        mock_message_sender: MagicMock,
        mock_player_repo: MagicMock,
        mock_map_resources: MagicMock,
    ) -> None:
        """Test no puede empezar a navegar si no hay agua cerca."""
        mock_map_resources.has_water = MagicMock(return_value=False)  # No hay agua
        data = bytes([0x1E, 0x01])
        task = TaskUseItem(
            data,
            mock_message_sender,
            slot=1,
            session_data={"user_id": 1},
            player_repo=mock_player_repo,
            map_resources=mock_map_resources,
        )

        with patch("src.tasks.inventory.task_use_item.InventoryRepository") as mock_inv_repo:
            mock_inv_repo_instance = MagicMock()
            mock_inv_repo_instance.get_slot = AsyncMock(return_value=(BOAT_ITEM_ID, 1))
            mock_inv_repo.return_value = mock_inv_repo_instance

            await task.execute()

            mock_message_sender.send_console_msg.assert_called_once_with(
                "Debes estar cerca del agua para comenzar a navegar."
            )
            mock_player_repo.set_sailing.assert_not_called()

    async def test_boat_cannot_start_sailing_no_position(
        self,
        mock_message_sender: MagicMock,
        mock_player_repo: MagicMock,
        mock_map_resources: MagicMock,
    ) -> None:
        """Test no puede empezar a navegar sin posición."""
        mock_player_repo.get_position = AsyncMock(return_value=None)  # Sin posición
        data = bytes([0x1E, 0x01])
        task = TaskUseItem(
            data,
            mock_message_sender,
            slot=1,
            session_data={"user_id": 1},
            player_repo=mock_player_repo,
            map_resources=mock_map_resources,
        )

        with patch("src.tasks.inventory.task_use_item.InventoryRepository") as mock_inv_repo:
            mock_inv_repo_instance = MagicMock()
            mock_inv_repo_instance.get_slot = AsyncMock(return_value=(BOAT_ITEM_ID, 1))
            mock_inv_repo.return_value = mock_inv_repo_instance

            await task.execute()

            mock_player_repo.set_sailing.assert_not_called()

    async def test_boat_stop_sailing_near_land(
        self,
        mock_message_sender: MagicMock,
        mock_player_repo: MagicMock,
        mock_map_resources: MagicMock,
        mock_account_repo: MagicMock,
    ) -> None:
        """Test puede dejar de navegar cerca de tierra."""
        mock_player_repo.is_sailing = AsyncMock(return_value=True)  # Ya está navegando
        mock_map_resources.has_water = MagicMock(return_value=False)  # No hay agua = tierra
        data = bytes([0x1E, 0x01])
        task = TaskUseItem(
            data,
            mock_message_sender,
            slot=1,
            session_data={"user_id": 1, "username": "test"},
            player_repo=mock_player_repo,
            map_resources=mock_map_resources,
            account_repo=mock_account_repo,
        )

        with patch("src.tasks.inventory.task_use_item.InventoryRepository") as mock_inv_repo:
            mock_inv_repo_instance = MagicMock()
            mock_inv_repo_instance.get_slot = AsyncMock(return_value=(BOAT_ITEM_ID, 1))
            mock_inv_repo.return_value = mock_inv_repo_instance

            await task.execute()

            mock_player_repo.set_sailing.assert_called_once_with(1, False)  # noqa: FBT003
            mock_message_sender.send_console_msg.assert_called_once_with(
                "Has cambiado al modo de caminata"
            )

    async def test_boat_stop_sailing_heading_land(
        self,
        mock_message_sender: MagicMock,
        mock_player_repo: MagicMock,
        mock_map_resources: MagicMock,
        mock_account_repo: MagicMock,
    ) -> None:
        """Test puede dejar de navegar si hay tierra en la dirección actual."""
        mock_player_repo.is_sailing = AsyncMock(return_value=True)
        # Agua en radio 1, pero tierra adelante
        mock_map_resources.has_water = MagicMock(
            side_effect=lambda _m, x, y: not (x == 50 and y == 49)  # Tierra adelante (Norte)
        )
        mock_player_repo.get_position = AsyncMock(
            return_value={"map": 1, "x": 50, "y": 50, "heading": HEADING_NORTH}
        )
        data = bytes([0x1E, 0x01])
        task = TaskUseItem(
            data,
            mock_message_sender,
            slot=1,
            session_data={"user_id": 1, "username": "test"},
            player_repo=mock_player_repo,
            map_resources=mock_map_resources,
            account_repo=mock_account_repo,
        )

        with patch("src.tasks.inventory.task_use_item.InventoryRepository") as mock_inv_repo:
            mock_inv_repo_instance = MagicMock()
            mock_inv_repo_instance.get_slot = AsyncMock(return_value=(BOAT_ITEM_ID, 1))
            mock_inv_repo.return_value = mock_inv_repo_instance

            await task.execute()

            mock_player_repo.set_sailing.assert_called_once_with(1, False)  # noqa: FBT003

    async def test_boat_cannot_stop_sailing_middle_water(
        self,
        mock_message_sender: MagicMock,
        mock_player_repo: MagicMock,
        mock_map_resources: MagicMock,
    ) -> None:
        """Test no puede dejar de navegar en medio del agua."""
        mock_player_repo.is_sailing = AsyncMock(return_value=True)
        # Simular que todo el área es agua
        mock_map_resources.has_water = MagicMock(return_value=True)
        data = bytes([0x1E, 0x01])
        task = TaskUseItem(
            data,
            mock_message_sender,
            slot=1,
            session_data={"user_id": 1},
            player_repo=mock_player_repo,
            map_resources=mock_map_resources,
        )

        with patch("src.tasks.inventory.task_use_item.InventoryRepository") as mock_inv_repo:
            mock_inv_repo_instance = MagicMock()
            mock_inv_repo_instance.get_slot = AsyncMock(return_value=(BOAT_ITEM_ID, 1))
            mock_inv_repo.return_value = mock_inv_repo_instance

            await task.execute()

            mock_message_sender.send_console_msg.assert_called_once_with(
                "No puedes dejar de navegar en medio del agua. Busca la costa."
            )
            mock_player_repo.set_sailing.assert_not_called()


@pytest.mark.asyncio
class TestTaskUseItemApple:
    """Tests para el consumo de manzanas."""

    async def test_apple_restore_hunger(
        self, mock_message_sender: MagicMock, mock_player_repo: MagicMock
    ) -> None:
        """Test que la manzana restaura hambre."""
        data = bytes([0x1E, 0x01])
        task = TaskUseItem(
            data,
            mock_message_sender,
            slot=1,
            session_data={"user_id": 1},
            player_repo=mock_player_repo,
        )

        with (
            patch("src.tasks.inventory.task_use_item.InventoryRepository") as mock_inv_repo,
            patch("src.tasks.inventory.task_use_item.get_item") as mock_get_item,
        ):
            mock_inv_repo_instance = MagicMock()
            mock_inv_repo_instance.get_slot = AsyncMock(return_value=(1, 5))
            mock_inv_repo_instance.remove_item = AsyncMock(return_value=True)
            mock_inv_repo.return_value = mock_inv_repo_instance

            mock_apple = MagicMock()
            mock_apple.name = "Manzana"
            mock_apple.graphic_id = 100
            mock_apple.item_type.to_client_type = MagicMock(return_value=6)
            mock_apple.max_damage = 0
            mock_apple.min_damage = 0
            mock_apple.defense = 0
            mock_apple.value = 10
            mock_get_item.return_value = mock_apple

            await task.execute()

            # Debe restaurar hambre (50 + 20 = 70, máximo 100)
            hunger_data = mock_player_repo.set_hunger_thirst.call_args[1]
            assert hunger_data["min_hunger"] == 70
            mock_message_sender.send_update_hunger_and_thirst.assert_called_once()

    async def test_apple_restore_hunger_max(
        self, mock_message_sender: MagicMock, mock_player_repo: MagicMock
    ) -> None:
        """Test que la manzana no excede el máximo de hambre."""
        mock_player_repo.get_hunger_thirst = AsyncMock(
            return_value={
                "min_hunger": 90,  # Casi lleno
                "max_hunger": 100,
                "min_water": 50,
                "max_water": 100,
            }
        )
        data = bytes([0x1E, 0x01])
        task = TaskUseItem(
            data,
            mock_message_sender,
            slot=1,
            session_data={"user_id": 1},
            player_repo=mock_player_repo,
        )

        with (
            patch("src.tasks.inventory.task_use_item.InventoryRepository") as mock_inv_repo,
            patch("src.tasks.inventory.task_use_item.get_item") as mock_get_item,
        ):
            mock_inv_repo_instance = MagicMock()
            mock_inv_repo_instance.get_slot = AsyncMock(return_value=(1, 5))
            mock_inv_repo_instance.remove_item = AsyncMock(return_value=True)
            mock_inv_repo.return_value = mock_inv_repo_instance

            mock_apple = MagicMock()
            mock_apple.name = "Manzana"
            mock_apple.graphic_id = 100
            mock_apple.item_type.to_client_type = MagicMock(return_value=6)
            mock_apple.max_damage = 0
            mock_apple.min_damage = 0
            mock_apple.defense = 0
            mock_apple.value = 10
            mock_get_item.return_value = mock_apple

            await task.execute()

            # Debe limitar a 100 (90 + 20 = 110, pero máximo es 100)
            hunger_data = mock_player_repo.set_hunger_thirst.call_args[1]
            assert hunger_data["min_hunger"] == 100

    async def test_apple_remove_fails(
        self, mock_message_sender: MagicMock, mock_player_repo: MagicMock
    ) -> None:
        """Test cuando falla remover la manzana del inventario."""
        data = bytes([0x1E, 0x01])
        task = TaskUseItem(
            data,
            mock_message_sender,
            slot=1,
            session_data={"user_id": 1},
            player_repo=mock_player_repo,
        )

        with patch("src.tasks.inventory.task_use_item.InventoryRepository") as mock_inv_repo:
            mock_inv_repo_instance = MagicMock()
            mock_inv_repo_instance.get_slot = AsyncMock(return_value=(1, 5))
            mock_inv_repo_instance.remove_item = AsyncMock(return_value=False)  # Falla
            mock_inv_repo.return_value = mock_inv_repo_instance

            await task.execute()

            # No debe restaurar hambre si falla
            mock_player_repo.set_hunger_thirst.assert_not_called()

    async def test_apple_no_hunger_data(
        self, mock_message_sender: MagicMock, mock_player_repo: MagicMock
    ) -> None:
        """Test cuando no hay datos de hambre/sed."""
        mock_player_repo.get_hunger_thirst = AsyncMock(return_value=None)
        data = bytes([0x1E, 0x01])
        task = TaskUseItem(
            data,
            mock_message_sender,
            slot=1,
            session_data={"user_id": 1},
            player_repo=mock_player_repo,
        )

        with (
            patch("src.tasks.inventory.task_use_item.InventoryRepository") as mock_inv_repo,
            patch("src.tasks.inventory.task_use_item.get_item") as mock_get_item,
        ):
            mock_inv_repo_instance = MagicMock()
            mock_inv_repo_instance.get_slot = AsyncMock(return_value=(1, 5))
            mock_inv_repo_instance.remove_item = AsyncMock(return_value=True)
            mock_inv_repo.return_value = mock_inv_repo_instance

            mock_apple = MagicMock()
            mock_apple.name = "Manzana"
            mock_apple.graphic_id = 100
            mock_apple.item_type.to_client_type = MagicMock(return_value=6)
            mock_apple.max_damage = 0
            mock_apple.min_damage = 0
            mock_apple.defense = 0
            mock_apple.value = 10
            mock_get_item.return_value = mock_apple

            await task.execute()

            mock_message_sender.send_console_msg.assert_any_call("No se pudo restaurar el hambre.")
