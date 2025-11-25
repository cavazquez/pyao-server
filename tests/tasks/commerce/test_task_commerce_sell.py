"""Tests para TaskCommerceSell."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.commands.base import CommandResult
from src.commands.commerce_sell_command import CommerceSellCommand
from src.tasks.commerce.task_commerce_sell import TaskCommerceSell


def create_mock_commerce_sell_handler(
    commerce_service: MagicMock | None = None,
    player_repo: MagicMock | None = None,
    inventory_repo: MagicMock | None = None,
    redis_client: MagicMock | None = None,
    message_sender: MagicMock | None = None,
) -> MagicMock:
    """Crea un mock de CommerceSellCommandHandler con las dependencias especificadas."""
    handler = MagicMock()
    handler.commerce_service = commerce_service or MagicMock()
    handler.player_repo = player_repo or MagicMock()
    handler.inventory_repo = inventory_repo or MagicMock()
    handler.redis_client = redis_client or MagicMock()
    handler.message_sender = message_sender or MagicMock()
    handler.handle = AsyncMock()
    return handler


@pytest.mark.asyncio
class TestTaskCommerceSell:
    """Tests para TaskCommerceSell."""

    async def test_sell_item_success(self) -> None:
        """Test de venta exitosa."""
        # Setup
        message_sender = MagicMock()
        message_sender.connection.address = "127.0.0.1:1234"
        message_sender.send_console_msg = AsyncMock()
        message_sender.send_update_gold = AsyncMock()

        commerce_sell_handler = create_mock_commerce_sell_handler(message_sender=message_sender)
        commerce_sell_handler.handle.return_value = CommandResult.ok(
            data={"npc_id": 2, "slot": 3, "quantity": 5, "success": True}
        )

        # Packet: COMMERCE_SELL + slot=3 + quantity=5
        data = bytes([0x2A, 0x03, 0x05, 0x00])  # 5 en little-endian
        session_data = {"user_id": 1}

        task = TaskCommerceSell(
            data,
            message_sender,
            slot=3,
            quantity=5,
            commerce_sell_handler=commerce_sell_handler,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert
        commerce_sell_handler.handle.assert_called_once()
        call_args = commerce_sell_handler.handle.call_args[0][0]
        assert isinstance(call_args, CommerceSellCommand)
        assert call_args.user_id == 1
        assert call_args.slot == 3
        assert call_args.quantity == 5

    async def test_sell_item_failure(self) -> None:
        """Test de venta fallida."""
        # Setup
        message_sender = MagicMock()
        message_sender.connection.address = "127.0.0.1:1234"
        message_sender.send_console_msg = AsyncMock()
        message_sender.send_update_gold = AsyncMock()

        commerce_sell_handler = create_mock_commerce_sell_handler(message_sender=message_sender)
        commerce_sell_handler.handle.return_value = CommandResult.error("No tienes ese item")

        data = bytes([0x2A, 0x03, 0x05, 0x00])
        session_data = {"user_id": 1}

        task = TaskCommerceSell(
            data,
            message_sender,
            slot=3,
            quantity=5,
            commerce_sell_handler=commerce_sell_handler,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert
        commerce_sell_handler.handle.assert_called_once()

    async def test_sell_without_session(self) -> None:
        """Test sin sesión activa."""
        # Setup
        message_sender = MagicMock()
        message_sender.send_console_msg = AsyncMock()

        commerce_sell_handler = create_mock_commerce_sell_handler(message_sender=message_sender)

        data = bytes([0x2A, 0x03, 0x05, 0x00])
        session_data = {}  # Sin user_id

        task = TaskCommerceSell(
            data,
            message_sender,
            slot=3,
            quantity=5,
            commerce_sell_handler=commerce_sell_handler,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert
        message_sender.send_console_msg.assert_called_with("Error: Sesión no válida")
        commerce_sell_handler.handle.assert_not_called()

    async def test_sell_without_handler(self) -> None:
        """Test sin handler."""
        # Setup
        message_sender = MagicMock()
        message_sender.connection.address = "127.0.0.1:1234"

        data = bytes([0x2A, 0x03, 0x05, 0x00])
        session_data = {"user_id": 1}

        task = TaskCommerceSell(
            data,
            message_sender,
            slot=3,
            quantity=5,
            commerce_sell_handler=None,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert - no debe crashear

    async def test_sell_without_active_merchant(self) -> None:
        """Test sin mercader activo."""
        # Setup
        message_sender = MagicMock()
        message_sender.connection.address = "127.0.0.1:1234"
        message_sender.send_console_msg = AsyncMock()

        commerce_sell_handler = create_mock_commerce_sell_handler(message_sender=message_sender)
        commerce_sell_handler.handle.return_value = CommandResult.error(
            "No tienes una ventana de comercio abierta"
        )

        data = bytes([0x2A, 0x03, 0x05, 0x00])
        session_data = {"user_id": 1}

        task = TaskCommerceSell(
            data,
            message_sender,
            slot=3,
            quantity=5,
            commerce_sell_handler=commerce_sell_handler,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert
        commerce_sell_handler.handle.assert_called_once()
