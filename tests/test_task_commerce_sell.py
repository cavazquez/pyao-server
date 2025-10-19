"""Tests para TaskCommerceSell."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.commerce_service import CommerceService
from src.inventory_repository import InventoryRepository
from src.player_repository import PlayerRepository
from src.redis_client import RedisClient
from src.task_commerce_sell import TaskCommerceSell


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

        commerce_service = MagicMock(spec=CommerceService)
        commerce_service.sell_item = AsyncMock(
            return_value=(True, "Vendiste 5x Poción por 250 oro")
        )

        player_repo = MagicMock(spec=PlayerRepository)
        player_repo.get_gold = AsyncMock(return_value=750)

        inventory_repo = MagicMock(spec=InventoryRepository)

        redis_client = MagicMock(spec=RedisClient)
        redis_client.redis.get = AsyncMock(return_value=b"2")  # NPC ID 2

        # Packet: COMMERCE_SELL + slot=3 + quantity=5
        data = bytes([0x2A, 0x03, 0x05, 0x00])  # 5 en little-endian

        session_data = {"user_id": 1}

        task = TaskCommerceSell(
            data,
            message_sender,
            commerce_service=commerce_service,
            player_repo=player_repo,
            inventory_repo=inventory_repo,
            redis_client=redis_client,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert
        commerce_service.sell_item.assert_called_once_with(1, 2, 3, 5)
        message_sender.send_console_msg.assert_called_with("Vendiste 5x Poción por 250 oro")
        message_sender.send_update_gold.assert_called_once_with(750)

    async def test_sell_item_failure(self) -> None:
        """Test de venta fallida."""
        # Setup
        message_sender = MagicMock()
        message_sender.connection.address = "127.0.0.1:1234"
        message_sender.send_console_msg = AsyncMock()
        message_sender.send_update_gold = AsyncMock()

        commerce_service = MagicMock(spec=CommerceService)
        commerce_service.sell_item = AsyncMock(return_value=(False, "No tienes ese item"))

        player_repo = MagicMock(spec=PlayerRepository)
        inventory_repo = MagicMock(spec=InventoryRepository)

        redis_client = MagicMock(spec=RedisClient)
        redis_client.redis.get = AsyncMock(return_value=b"2")

        data = bytes([0x2A, 0x03, 0x05, 0x00])
        session_data = {"user_id": 1}

        task = TaskCommerceSell(
            data,
            message_sender,
            commerce_service=commerce_service,
            player_repo=player_repo,
            inventory_repo=inventory_repo,
            redis_client=redis_client,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert
        message_sender.send_console_msg.assert_called_with("No tienes ese item")
        message_sender.send_update_gold.assert_not_called()

    async def test_sell_without_session(self) -> None:
        """Test sin sesión activa."""
        # Setup
        message_sender = MagicMock()
        message_sender.send_console_msg = AsyncMock()

        commerce_service = MagicMock(spec=CommerceService)

        data = bytes([0x2A, 0x03, 0x05, 0x00])
        session_data = {}  # Sin user_id

        task = TaskCommerceSell(
            data,
            message_sender,
            commerce_service=commerce_service,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert
        message_sender.send_console_msg.assert_called_with("Error: Sesión no válida")

    async def test_sell_without_dependencies(self) -> None:
        """Test sin dependencias necesarias."""
        # Setup
        message_sender = MagicMock()
        message_sender.connection.address = "127.0.0.1:1234"

        data = bytes([0x2A, 0x03, 0x05, 0x00])
        session_data = {"user_id": 1}

        task = TaskCommerceSell(
            data,
            message_sender,
            commerce_service=None,  # Sin dependencias
            player_repo=None,
            inventory_repo=None,
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

        commerce_service = MagicMock(spec=CommerceService)
        player_repo = MagicMock(spec=PlayerRepository)
        inventory_repo = MagicMock(spec=InventoryRepository)

        redis_client = MagicMock(spec=RedisClient)
        redis_client.redis.get = AsyncMock(return_value=None)  # Sin mercader activo

        data = bytes([0x2A, 0x03, 0x05, 0x00])
        session_data = {"user_id": 1}

        task = TaskCommerceSell(
            data,
            message_sender,
            commerce_service=commerce_service,
            player_repo=player_repo,
            inventory_repo=inventory_repo,
            redis_client=redis_client,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert
        message_sender.send_console_msg.assert_called_with(
            "No tienes una ventana de comercio abierta"
        )
        commerce_service.sell_item.assert_not_called()
