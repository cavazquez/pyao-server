"""Tests para TaskPickup."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.commands.base import CommandResult
from src.commands.pickup_command import PickupCommand
from src.tasks.interaction.task_pickup import TaskPickup


def create_mock_pickup_handler(
    player_repo: MagicMock | None = None,
    inventory_repo: MagicMock | None = None,
    map_manager: MagicMock | None = None,
    broadcast_service: MagicMock | None = None,
    item_catalog: MagicMock | None = None,
    party_service: MagicMock | None = None,
    message_sender: MagicMock | None = None,
) -> MagicMock:
    """Crea un mock de PickupCommandHandler con las dependencias especificadas."""
    handler = MagicMock()
    handler.player_repo = player_repo or MagicMock()
    handler.inventory_repo = inventory_repo
    handler.map_manager = map_manager or MagicMock()
    handler.broadcast_service = broadcast_service
    handler.item_catalog = item_catalog
    handler.party_service = party_service
    handler.message_sender = message_sender or MagicMock()
    handler.handle = AsyncMock()
    return handler


@pytest.mark.asyncio
class TestTaskPickup:
    """Tests para TaskPickup."""

    async def test_pickup_gold_success(self) -> None:
        """Test de recogida de oro exitosa."""
        # Setup
        message_sender = MagicMock()
        message_sender.send_console_msg = AsyncMock()
        message_sender.send_update_user_stats = AsyncMock()

        pickup_handler = create_mock_pickup_handler(message_sender=message_sender)
        pickup_handler.handle.return_value = CommandResult.ok(
            data={"item_id": 1, "quantity": 100, "type": "gold"}
        )

        data = bytes([0x11])  # PICKUP packet
        session_data = {"user_id": 1}

        task = TaskPickup(
            data,
            message_sender,
            pickup_handler=pickup_handler,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert
        pickup_handler.handle.assert_called_once()
        call_args = pickup_handler.handle.call_args[0][0]
        assert isinstance(call_args, PickupCommand)
        assert call_args.user_id == 1

    async def test_pickup_item_success(self) -> None:
        """Test de recogida de item exitosa."""
        # Setup
        message_sender = MagicMock()
        message_sender.send_console_msg = AsyncMock()
        message_sender.send_change_inventory_slot = AsyncMock()

        pickup_handler = create_mock_pickup_handler(message_sender=message_sender)
        pickup_handler.handle.return_value = CommandResult.ok(
            data={"item_id": 10, "quantity": 5, "type": "item", "slots": [(1, 5)]}
        )

        data = bytes([0x11])
        session_data = {"user_id": 1}

        task = TaskPickup(
            data,
            message_sender,
            pickup_handler=pickup_handler,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert
        pickup_handler.handle.assert_called_once()
        call_args = pickup_handler.handle.call_args[0][0]
        assert isinstance(call_args, PickupCommand)
        assert call_args.user_id == 1

    async def test_pickup_no_items_on_ground(self) -> None:
        """Test de recogida cuando no hay items en el suelo."""
        # Setup
        message_sender = MagicMock()
        message_sender.send_console_msg = AsyncMock()

        pickup_handler = create_mock_pickup_handler(message_sender=message_sender)
        pickup_handler.handle.return_value = CommandResult.error("No hay nada aquí")

        data = bytes([0x11])
        session_data = {"user_id": 1}

        task = TaskPickup(
            data,
            message_sender,
            pickup_handler=pickup_handler,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert
        pickup_handler.handle.assert_called_once()

    async def test_pickup_inventory_full(self) -> None:
        """Test de recogida con inventario lleno."""
        # Setup
        message_sender = MagicMock()
        message_sender.send_console_msg = AsyncMock()

        pickup_handler = create_mock_pickup_handler(message_sender=message_sender)
        pickup_handler.handle.return_value = CommandResult.error("Inventario lleno")

        data = bytes([0x11])
        session_data = {"user_id": 1}

        task = TaskPickup(
            data,
            message_sender,
            pickup_handler=pickup_handler,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert
        pickup_handler.handle.assert_called_once()

    async def test_pickup_without_session(self) -> None:
        """Test de recogida sin sesión activa."""
        # Setup
        message_sender = MagicMock()
        pickup_handler = create_mock_pickup_handler(message_sender=message_sender)

        data = bytes([0x11])
        session_data = {}  # Sin user_id

        task = TaskPickup(
            data, message_sender, pickup_handler=pickup_handler, session_data=session_data
        )

        # Execute
        await task.execute()

        # Assert
        pickup_handler.handle.assert_not_called()

    async def test_pickup_without_handler(self) -> None:
        """Test sin handler."""
        # Setup
        message_sender = MagicMock()

        data = bytes([0x11])
        session_data = {"user_id": 1}

        task = TaskPickup(
            data,
            message_sender,
            pickup_handler=None,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert - no debe crashear

    async def test_pickup_position_not_found(self) -> None:
        """Test cuando no se encuentra la posición del jugador."""
        # Setup
        message_sender = MagicMock()

        pickup_handler = create_mock_pickup_handler(message_sender=message_sender)
        pickup_handler.handle.return_value = CommandResult.error(
            "No se pudo obtener la posición del jugador"
        )

        data = bytes([0x11])
        session_data = {"user_id": 1}

        task = TaskPickup(
            data,
            message_sender,
            pickup_handler=pickup_handler,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert
        pickup_handler.handle.assert_called_once()

    async def test_pickup_item_not_in_catalog(self) -> None:
        """Test de recogida de item que no está en el catálogo."""
        # Setup
        message_sender = MagicMock()

        pickup_handler = create_mock_pickup_handler(message_sender=message_sender)
        pickup_handler.handle.return_value = CommandResult.error(
            "Item 999 no encontrado en el catálogo"
        )

        data = bytes([0x11])
        session_data = {"user_id": 1}

        task = TaskPickup(
            data,
            message_sender,
            pickup_handler=pickup_handler,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert
        pickup_handler.handle.assert_called_once()

    async def test_pickup_gold_stats_not_found(self) -> None:
        """Test de recogida de oro cuando no se encuentran stats."""
        # Setup
        message_sender = MagicMock()

        pickup_handler = create_mock_pickup_handler(message_sender=message_sender)
        pickup_handler.handle.return_value = CommandResult.error(
            "No se pudieron obtener los stats del jugador"
        )

        data = bytes([0x11])
        session_data = {"user_id": 1}

        task = TaskPickup(
            data,
            message_sender,
            pickup_handler=pickup_handler,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert
        pickup_handler.handle.assert_called_once()
