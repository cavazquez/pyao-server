"""Tests para TaskPickup."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.repositories.inventory_repository import InventoryRepository
from src.item_catalog import ItemCatalog
from src.item_constants import GOLD_ITEM_ID
from src.map_manager import MapManager
from src.services.multiplayer_broadcast_service import MultiplayerBroadcastService
from src.repositories.player_repository import PlayerRepository
from src.task_pickup import TaskPickup


@pytest.mark.asyncio
class TestTaskPickup:
    """Tests para TaskPickup."""

    async def test_pickup_gold_success(self) -> None:
        """Test de recogida de oro exitosa."""
        # Setup
        message_sender = MagicMock()
        message_sender.send_console_msg = AsyncMock()
        message_sender.send_update_user_stats = AsyncMock()

        player_repo = MagicMock(spec=PlayerRepository)
        player_repo.get_position = AsyncMock(return_value={"map": 1, "x": 50, "y": 50})
        player_repo.get_stats = AsyncMock(
            side_effect=[
                {
                    "gold": 100,
                    "max_hp": 100,
                    "min_hp": 100,
                    "max_mana": 50,
                    "min_mana": 50,
                    "max_sta": 100,
                    "min_sta": 100,
                    "level": 5,
                    "elu": 500,
                    "exp": 1000,
                },
                {
                    "gold": 200,
                    "max_hp": 100,
                    "min_hp": 100,
                    "max_mana": 50,
                    "min_mana": 50,
                    "max_sta": 100,
                    "min_sta": 100,
                    "level": 5,
                    "elu": 500,
                    "exp": 1000,
                },
            ]
        )
        player_repo.update_gold = AsyncMock()

        map_manager = MagicMock(spec=MapManager)
        map_manager.get_ground_items = MagicMock(
            return_value=[{"item_id": GOLD_ITEM_ID, "quantity": 100}]
        )
        map_manager.remove_ground_item = MagicMock()

        broadcast_service = MagicMock(spec=MultiplayerBroadcastService)
        broadcast_service.broadcast_object_delete = AsyncMock()

        data = bytes([0x11])  # PICKUP packet

        session_data = {"user_id": 1}

        task = TaskPickup(
            data,
            message_sender,
            player_repo=player_repo,
            map_manager=map_manager,
            broadcast_service=broadcast_service,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert
        player_repo.update_gold.assert_called_once_with(1, 200)
        map_manager.remove_ground_item.assert_called_once_with(1, 50, 50, item_index=0)
        broadcast_service.broadcast_object_delete.assert_called_once_with(1, 50, 50)
        message_sender.send_console_msg.assert_called_with("Recogiste 100 monedas de oro.")

    async def test_pickup_item_success(self) -> None:
        """Test de recogida de item exitosa."""
        # Setup
        message_sender = MagicMock()
        message_sender.send_console_msg = AsyncMock()
        message_sender.send_change_inventory_slot = AsyncMock()

        player_repo = MagicMock(spec=PlayerRepository)
        player_repo.get_position = AsyncMock(return_value={"map": 1, "x": 50, "y": 50})

        inventory_repo = MagicMock(spec=InventoryRepository)
        inventory_repo.add_item = AsyncMock(return_value=[(1, 5)])  # Slot 1, cantidad 5

        map_manager = MagicMock(spec=MapManager)
        map_manager.get_ground_items = MagicMock(
            return_value=[{"item_id": 10, "quantity": 5}]  # Item ID 10
        )
        map_manager.remove_ground_item = MagicMock()

        broadcast_service = MagicMock(spec=MultiplayerBroadcastService)
        broadcast_service.broadcast_object_delete = AsyncMock()

        item_catalog = MagicMock(spec=ItemCatalog)
        item_catalog.get_item_data = MagicMock(
            return_value={
                "Name": "Poción Roja",
                "GrhIndex": 100,
                "ObjType": 2,
                "MaxHit": 0,
                "MinHit": 0,
                "MaxDef": 0,
                "MinDef": 0,
                "Valor": 50,
            }
        )

        data = bytes([0x11])

        session_data = {"user_id": 1}

        task = TaskPickup(
            data,
            message_sender,
            player_repo=player_repo,
            inventory_repo=inventory_repo,
            map_manager=map_manager,
            broadcast_service=broadcast_service,
            item_catalog=item_catalog,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert
        inventory_repo.add_item.assert_called_once_with(1, 10, 5)
        message_sender.send_change_inventory_slot.assert_called_once()
        message_sender.send_console_msg.assert_called_with("Recogiste 5x Poción Roja.")
        map_manager.remove_ground_item.assert_called_once()

    async def test_pickup_no_items_on_ground(self) -> None:
        """Test de recogida cuando no hay items en el suelo."""
        # Setup
        message_sender = MagicMock()
        message_sender.send_console_msg = AsyncMock()

        player_repo = MagicMock(spec=PlayerRepository)
        player_repo.get_position = AsyncMock(return_value={"map": 1, "x": 50, "y": 50})

        map_manager = MagicMock(spec=MapManager)
        map_manager.get_ground_items = MagicMock(return_value=[])  # Sin items

        data = bytes([0x11])

        session_data = {"user_id": 1}

        task = TaskPickup(
            data,
            message_sender,
            player_repo=player_repo,
            map_manager=map_manager,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert
        message_sender.send_console_msg.assert_called_with("No hay nada aquí.")

    async def test_pickup_inventory_full(self) -> None:
        """Test de recogida con inventario lleno."""
        # Setup
        message_sender = MagicMock()
        message_sender.send_console_msg = AsyncMock()

        player_repo = MagicMock(spec=PlayerRepository)
        player_repo.get_position = AsyncMock(return_value={"map": 1, "x": 50, "y": 50})

        inventory_repo = MagicMock(spec=InventoryRepository)
        inventory_repo.add_item = AsyncMock(return_value=[])  # No hay espacio

        map_manager = MagicMock(spec=MapManager)
        map_manager.get_ground_items = MagicMock(return_value=[{"item_id": 10, "quantity": 5}])

        item_catalog = MagicMock(spec=ItemCatalog)
        item_catalog.get_item_data = MagicMock(return_value={"Name": "Poción"})

        data = bytes([0x11])

        session_data = {"user_id": 1}

        task = TaskPickup(
            data,
            message_sender,
            player_repo=player_repo,
            inventory_repo=inventory_repo,
            map_manager=map_manager,
            item_catalog=item_catalog,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert
        message_sender.send_console_msg.assert_called_with("Tu inventario está lleno.")
        map_manager.remove_ground_item.assert_not_called()

    async def test_pickup_without_session(self) -> None:
        """Test de recogida sin sesión activa."""
        # Setup
        message_sender = MagicMock()
        player_repo = MagicMock(spec=PlayerRepository)

        data = bytes([0x11])
        session_data = {}  # Sin user_id

        task = TaskPickup(data, message_sender, player_repo=player_repo, session_data=session_data)

        # Execute
        await task.execute()

        # Assert
        player_repo.get_position.assert_not_called()

    async def test_pickup_without_dependencies(self) -> None:
        """Test sin dependencias necesarias."""
        # Setup
        message_sender = MagicMock()

        data = bytes([0x11])
        session_data = {"user_id": 1}

        task = TaskPickup(
            data,
            message_sender,
            player_repo=None,  # Sin dependencias
            map_manager=None,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert - no debe crashear

    async def test_pickup_position_not_found(self) -> None:
        """Test cuando no se encuentra la posición del jugador."""
        # Setup
        message_sender = MagicMock()

        player_repo = MagicMock(spec=PlayerRepository)
        player_repo.get_position = AsyncMock(return_value=None)  # No encontrado

        map_manager = MagicMock(spec=MapManager)

        data = bytes([0x11])
        session_data = {"user_id": 1}

        task = TaskPickup(
            data,
            message_sender,
            player_repo=player_repo,
            map_manager=map_manager,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert
        map_manager.get_ground_items.assert_not_called()

    async def test_pickup_item_not_in_catalog(self) -> None:
        """Test de recogida de item que no está en el catálogo."""
        # Setup
        message_sender = MagicMock()

        player_repo = MagicMock(spec=PlayerRepository)
        player_repo.get_position = AsyncMock(return_value={"map": 1, "x": 50, "y": 50})

        inventory_repo = MagicMock(spec=InventoryRepository)

        map_manager = MagicMock(spec=MapManager)
        map_manager.get_ground_items = MagicMock(
            return_value=[{"item_id": 999, "quantity": 1}]  # Item desconocido
        )

        item_catalog = MagicMock(spec=ItemCatalog)
        item_catalog.get_item_data = MagicMock(return_value=None)  # No encontrado

        data = bytes([0x11])
        session_data = {"user_id": 1}

        task = TaskPickup(
            data,
            message_sender,
            player_repo=player_repo,
            inventory_repo=inventory_repo,
            map_manager=map_manager,
            item_catalog=item_catalog,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert
        inventory_repo.add_item.assert_not_called()

    async def test_pickup_gold_stats_not_found(self) -> None:
        """Test de recogida de oro cuando no se encuentran stats."""
        # Setup
        message_sender = MagicMock()

        player_repo = MagicMock(spec=PlayerRepository)
        player_repo.get_position = AsyncMock(return_value={"map": 1, "x": 50, "y": 50})
        player_repo.get_stats = AsyncMock(return_value=None)  # No encontrado

        map_manager = MagicMock(spec=MapManager)
        map_manager.get_ground_items = MagicMock(
            return_value=[{"item_id": GOLD_ITEM_ID, "quantity": 100}]
        )

        data = bytes([0x11])
        session_data = {"user_id": 1}

        task = TaskPickup(
            data,
            message_sender,
            player_repo=player_repo,
            map_manager=map_manager,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert
        player_repo.update_gold.assert_not_called()
