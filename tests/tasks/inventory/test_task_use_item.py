"""Tests para TaskUseItem."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.commands.base import CommandResult
from src.commands.use_item_command import UseItemCommand
from src.models.item_constants import BOAT_ITEM_ID
from src.tasks.inventory.task_use_item import TaskUseItem


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


def create_mock_use_item_handler(
    player_repo: MagicMock | None = None,
    map_resources: MagicMock | None = None,
    account_repo: MagicMock | None = None,
    message_sender: MagicMock | None = None,
) -> MagicMock:
    """Crea un mock de UseItemCommandHandler con las dependencias especificadas."""
    handler = MagicMock()
    handler.player_repo = player_repo or MagicMock()
    handler.map_resources = map_resources
    handler.account_repo = account_repo
    handler.message_sender = message_sender or MagicMock()
    handler.handle = AsyncMock()
    return handler


@pytest.mark.asyncio
class TestTaskUseItemExecute:
    """Tests para el método execute de TaskUseItem."""

    async def test_execute_without_session(self, mock_message_sender: MagicMock) -> None:
        """Test sin sesión activa."""
        use_item_handler = create_mock_use_item_handler(message_sender=mock_message_sender)
        data = bytes([0x1E, 0x01])  # USE_ITEM + slot=1
        task = TaskUseItem(
            data,
            mock_message_sender,
            slot=1,
            use_item_handler=use_item_handler,
            session_data=None,
        )

        await task.execute()

        # No debe llamar al handler si no hay sesión
        use_item_handler.handle.assert_not_called()

    async def test_execute_without_handler(self, mock_message_sender: MagicMock) -> None:
        """Test sin handler."""
        data = bytes([0x1E, 0x01])
        task = TaskUseItem(
            data,
            mock_message_sender,
            slot=1,
            use_item_handler=None,
            session_data={"user_id": 1},
        )

        await task.execute()

        # No debe crashear

    async def test_execute_empty_slot(self, mock_message_sender: MagicMock) -> None:
        """Test cuando el slot está vacío."""
        use_item_handler = create_mock_use_item_handler(message_sender=mock_message_sender)
        use_item_handler.handle.return_value = CommandResult.error("El slot está vacío")
        data = bytes([0x1E, 0x01])
        task = TaskUseItem(
            data,
            mock_message_sender,
            slot=1,
            use_item_handler=use_item_handler,
            session_data={"user_id": 1},
        )

        await task.execute()

        # Debe llamar al handler (la validación de slot vacío está en el handler)
        use_item_handler.handle.assert_called_once()

    async def test_execute_work_tool(self, mock_message_sender: MagicMock) -> None:
        """Test usar herramienta de trabajo."""
        use_item_handler = create_mock_use_item_handler(message_sender=mock_message_sender)
        use_item_handler.handle.return_value = CommandResult.ok(
            data={"item_id": 561, "skill_type": 9, "handled": True}
        )
        data = bytes([0x1E, 0x01])
        task = TaskUseItem(
            data,
            mock_message_sender,
            slot=1,
            use_item_handler=use_item_handler,
            session_data={"user_id": 1},
        )

        await task.execute()

        # Debe llamar al handler
        use_item_handler.handle.assert_called_once()
        call_args = use_item_handler.handle.call_args[0][0]
        assert isinstance(call_args, UseItemCommand)
        assert call_args.user_id == 1
        assert call_args.slot == 1

    async def test_execute_work_tool_not_equipped(self, mock_message_sender: MagicMock) -> None:
        """Test usar herramienta de trabajo sin equipar."""
        use_item_handler = create_mock_use_item_handler(message_sender=mock_message_sender)
        use_item_handler.handle.return_value = CommandResult.error(
            "Debes tener equipada la herramienta para trabajar."
        )
        data = bytes([0x1E, 0x01])
        task = TaskUseItem(
            data,
            mock_message_sender,
            slot=1,
            use_item_handler=use_item_handler,
            session_data={"user_id": 1},
        )

        await task.execute()

        # Debe llamar al handler (la validación está en el handler)
        use_item_handler.handle.assert_called_once()

    async def test_execute_boat(
        self,
        mock_message_sender: MagicMock,
        mock_map_resources: MagicMock,
        mock_account_repo: MagicMock,
    ) -> None:
        """Test usar barca para entrar en modo navegación."""
        use_item_handler = create_mock_use_item_handler(
            message_sender=mock_message_sender,
            map_resources=mock_map_resources,
            account_repo=mock_account_repo,
        )
        use_item_handler.handle.return_value = CommandResult.ok(
            data={"item_id": BOAT_ITEM_ID, "is_sailing": True, "handled": True}
        )
        data = bytes([0x1E, 0x01])
        task = TaskUseItem(
            data,
            mock_message_sender,
            slot=1,
            use_item_handler=use_item_handler,
            session_data={"user_id": 1, "username": "test"},
        )

        await task.execute()

        # Debe llamar al handler
        use_item_handler.handle.assert_called_once()
        call_args = use_item_handler.handle.call_args[0][0]
        assert isinstance(call_args, UseItemCommand)
        assert call_args.user_id == 1
        assert call_args.slot == 1
        assert call_args.username == "test"

    async def test_execute_apple_consumption(self, mock_message_sender: MagicMock) -> None:
        """Test consumir manzana."""
        use_item_handler = create_mock_use_item_handler(message_sender=mock_message_sender)
        use_item_handler.handle.return_value = CommandResult.ok(
            data={"item_id": 1, "quantity_remaining": 4, "handled": True}
        )
        data = bytes([0x1E, 0x01])
        task = TaskUseItem(
            data,
            mock_message_sender,
            slot=1,
            use_item_handler=use_item_handler,
            session_data={"user_id": 1},
        )

        await task.execute()

        # Debe llamar al handler
        use_item_handler.handle.assert_called_once()
        call_args = use_item_handler.handle.call_args[0][0]
        assert isinstance(call_args, UseItemCommand)
        assert call_args.user_id == 1
        assert call_args.slot == 1

    async def test_execute_apple_last_one(self, mock_message_sender: MagicMock) -> None:
        """Test consumir última manzana (clear_slot)."""
        use_item_handler = create_mock_use_item_handler(message_sender=mock_message_sender)
        use_item_handler.handle.return_value = CommandResult.ok(
            data={"item_id": 1, "quantity_remaining": 0, "handled": True}
        )
        data = bytes([0x1E, 0x01])
        task = TaskUseItem(
            data,
            mock_message_sender,
            slot=1,
            use_item_handler=use_item_handler,
            session_data={"user_id": 1},
        )

        await task.execute()

        # Debe llamar al handler
        use_item_handler.handle.assert_called_once()

    async def test_execute_unknown_item(self, mock_message_sender: MagicMock) -> None:
        """Test usar item sin comportamiento definido."""
        use_item_handler = create_mock_use_item_handler(message_sender=mock_message_sender)
        use_item_handler.handle.return_value = CommandResult.ok(
            data={"item_id": 999, "handled": False}
        )
        data = bytes([0x1E, 0x01])
        task = TaskUseItem(
            data,
            mock_message_sender,
            slot=1,
            use_item_handler=use_item_handler,
            session_data={"user_id": 1},
        )

        await task.execute()

        # Debe llamar al handler
        use_item_handler.handle.assert_called_once()


@pytest.mark.asyncio
class TestTaskUseItemBoat:
    """Tests para el manejo de barca/navegación."""

    async def test_boat_cannot_start_sailing_no_water(
        self,
        mock_message_sender: MagicMock,
        mock_map_resources: MagicMock,
    ) -> None:
        """Test no puede empezar a navegar si no hay agua cerca."""
        use_item_handler = create_mock_use_item_handler(
            message_sender=mock_message_sender, map_resources=mock_map_resources
        )
        use_item_handler.handle.return_value = CommandResult.error(
            "Debes estar cerca del agua para comenzar a navegar."
        )
        data = bytes([0x1E, 0x01])
        task = TaskUseItem(
            data,
            mock_message_sender,
            slot=1,
            use_item_handler=use_item_handler,
            session_data={"user_id": 1},
        )

        await task.execute()

        # Debe llamar al handler (la validación está en el handler)
        use_item_handler.handle.assert_called_once()

    async def test_boat_cannot_start_sailing_no_position(
        self,
        mock_message_sender: MagicMock,
        mock_map_resources: MagicMock,
    ) -> None:
        """Test no puede empezar a navegar sin posición."""
        use_item_handler = create_mock_use_item_handler(
            message_sender=mock_message_sender, map_resources=mock_map_resources
        )
        use_item_handler.handle.return_value = CommandResult.error(
            "Error interno: repositorio no disponible"
        )
        data = bytes([0x1E, 0x01])
        task = TaskUseItem(
            data,
            mock_message_sender,
            slot=1,
            use_item_handler=use_item_handler,
            session_data={"user_id": 1},
        )

        await task.execute()

        # Debe llamar al handler
        use_item_handler.handle.assert_called_once()

    async def test_boat_stop_sailing_near_land(
        self,
        mock_message_sender: MagicMock,
        mock_map_resources: MagicMock,
        mock_account_repo: MagicMock,
    ) -> None:
        """Test puede dejar de navegar cerca de tierra."""
        use_item_handler = create_mock_use_item_handler(
            message_sender=mock_message_sender,
            map_resources=mock_map_resources,
            account_repo=mock_account_repo,
        )
        use_item_handler.handle.return_value = CommandResult.ok(
            data={"item_id": BOAT_ITEM_ID, "is_sailing": False, "handled": True}
        )
        data = bytes([0x1E, 0x01])
        task = TaskUseItem(
            data,
            mock_message_sender,
            slot=1,
            use_item_handler=use_item_handler,
            session_data={"user_id": 1, "username": "test"},
        )

        await task.execute()

        # Debe llamar al handler
        use_item_handler.handle.assert_called_once()

    async def test_boat_stop_sailing_heading_land(
        self,
        mock_message_sender: MagicMock,
        mock_map_resources: MagicMock,
        mock_account_repo: MagicMock,
    ) -> None:
        """Test puede dejar de navegar si hay tierra en la dirección actual."""
        use_item_handler = create_mock_use_item_handler(
            message_sender=mock_message_sender,
            map_resources=mock_map_resources,
            account_repo=mock_account_repo,
        )
        use_item_handler.handle.return_value = CommandResult.ok(
            data={"item_id": BOAT_ITEM_ID, "is_sailing": False, "handled": True}
        )
        data = bytes([0x1E, 0x01])
        task = TaskUseItem(
            data,
            mock_message_sender,
            slot=1,
            use_item_handler=use_item_handler,
            session_data={"user_id": 1, "username": "test"},
        )

        await task.execute()

        # Debe llamar al handler
        use_item_handler.handle.assert_called_once()

    async def test_boat_cannot_stop_sailing_middle_water(
        self,
        mock_message_sender: MagicMock,
        mock_map_resources: MagicMock,
    ) -> None:
        """Test no puede dejar de navegar en medio del agua."""
        use_item_handler = create_mock_use_item_handler(
            message_sender=mock_message_sender, map_resources=mock_map_resources
        )
        use_item_handler.handle.return_value = CommandResult.error(
            "No puedes dejar de navegar en medio del agua. Busca la costa."
        )
        data = bytes([0x1E, 0x01])
        task = TaskUseItem(
            data,
            mock_message_sender,
            slot=1,
            use_item_handler=use_item_handler,
            session_data={"user_id": 1},
        )

        await task.execute()

        # Debe llamar al handler (la validación está en el handler)
        use_item_handler.handle.assert_called_once()


@pytest.mark.asyncio
class TestTaskUseItemApple:
    """Tests para el consumo de manzanas."""

    async def test_apple_restore_hunger(self, mock_message_sender: MagicMock) -> None:
        """Test que la manzana restaura hambre."""
        use_item_handler = create_mock_use_item_handler(message_sender=mock_message_sender)
        use_item_handler.handle.return_value = CommandResult.ok(
            data={"item_id": 1, "quantity_remaining": 4, "handled": True}
        )
        data = bytes([0x1E, 0x01])
        task = TaskUseItem(
            data,
            mock_message_sender,
            slot=1,
            use_item_handler=use_item_handler,
            session_data={"user_id": 1},
        )

        await task.execute()

        # Debe llamar al handler (la restauración de hambre está en el handler)
        use_item_handler.handle.assert_called_once()

    async def test_apple_restore_hunger_max(self, mock_message_sender: MagicMock) -> None:
        """Test que la manzana no excede el máximo de hambre."""
        use_item_handler = create_mock_use_item_handler(message_sender=mock_message_sender)
        use_item_handler.handle.return_value = CommandResult.ok(
            data={"item_id": 1, "quantity_remaining": 4, "handled": True}
        )
        data = bytes([0x1E, 0x01])
        task = TaskUseItem(
            data,
            mock_message_sender,
            slot=1,
            use_item_handler=use_item_handler,
            session_data={"user_id": 1},
        )

        await task.execute()

        # Debe llamar al handler (la validación de máximo está en el handler)
        use_item_handler.handle.assert_called_once()

    async def test_apple_remove_fails(self, mock_message_sender: MagicMock) -> None:
        """Test cuando falla remover la manzana del inventario."""
        use_item_handler = create_mock_use_item_handler(message_sender=mock_message_sender)
        use_item_handler.handle.return_value = CommandResult.error("No se pudo consumir el item")
        data = bytes([0x1E, 0x01])
        task = TaskUseItem(
            data,
            mock_message_sender,
            slot=1,
            use_item_handler=use_item_handler,
            session_data={"user_id": 1},
        )

        await task.execute()

        # Debe llamar al handler (la validación está en el handler)
        use_item_handler.handle.assert_called_once()

    async def test_apple_no_hunger_data(self, mock_message_sender: MagicMock) -> None:
        """Test cuando no hay datos de hambre/sed."""
        use_item_handler = create_mock_use_item_handler(message_sender=mock_message_sender)
        use_item_handler.handle.return_value = CommandResult.error("No se pudo restaurar el hambre")
        data = bytes([0x1E, 0x01])
        task = TaskUseItem(
            data,
            mock_message_sender,
            slot=1,
            use_item_handler=use_item_handler,
            session_data={"user_id": 1},
        )

        await task.execute()

        # Debe llamar al handler (la validación está en el handler)
        use_item_handler.handle.assert_called_once()
