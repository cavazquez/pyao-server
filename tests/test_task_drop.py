"""Tests para TaskDrop."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.map_manager import MapManager
from src.multiplayer_broadcast_service import MultiplayerBroadcastService
from src.repositories.player_repository import PlayerRepository
from src.tasks.inventory.task_drop import TaskDrop


@pytest.mark.asyncio
class TestTaskDrop:
    """Tests para TaskDrop."""

    async def test_drop_gold_success(self) -> None:
        """Test de drop de oro exitoso."""
        # Setup
        message_sender = MagicMock()
        message_sender.send_console_msg = AsyncMock()
        message_sender.send_update_user_stats = AsyncMock()

        player_repo = MagicMock(spec=PlayerRepository)
        player_repo.get_stats = AsyncMock(
            side_effect=[
                {
                    "gold": 1000,
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
                    "gold": 900,
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
        player_repo.get_position = AsyncMock(return_value={"map": 1, "x": 50, "y": 50})
        player_repo.update_gold = AsyncMock()

        map_manager = MagicMock(spec=MapManager)
        map_manager.add_ground_item = MagicMock()

        broadcast_service = MagicMock(spec=MultiplayerBroadcastService)
        broadcast_service.broadcast_object_create = AsyncMock()

        # Packet: DROP + slot=1 + quantity=100
        data = bytes([0x10, 0x01, 0x64, 0x00])  # 100 en little-endian

        session_data = {"user_id": 1}

        task = TaskDrop(
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
        player_repo.update_gold.assert_called_once_with(1, 900)
        map_manager.add_ground_item.assert_called_once()
        broadcast_service.broadcast_object_create.assert_called_once()
        message_sender.send_console_msg.assert_called_with("Tiraste 100 monedas de oro al suelo.")
        message_sender.send_update_user_stats.assert_called_once()

    async def test_drop_gold_more_than_available(self) -> None:
        """Test de drop de más oro del que se tiene."""
        # Setup
        message_sender = MagicMock()
        message_sender.send_console_msg = AsyncMock()
        message_sender.send_update_user_stats = AsyncMock()

        player_repo = MagicMock(spec=PlayerRepository)
        player_repo.get_stats = AsyncMock(
            side_effect=[
                {
                    "gold": 50,
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
                    "gold": 0,
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
        player_repo.get_position = AsyncMock(return_value={"map": 1, "x": 50, "y": 50})
        player_repo.update_gold = AsyncMock()

        map_manager = MagicMock(spec=MapManager)
        map_manager.add_ground_item = MagicMock()

        broadcast_service = MagicMock(spec=MultiplayerBroadcastService)
        broadcast_service.broadcast_object_create = AsyncMock()

        # Packet: DROP + slot=1 + quantity=100 (pero solo tiene 50)
        data = bytes([0x10, 0x01, 0x64, 0x00])

        session_data = {"user_id": 1}

        task = TaskDrop(
            data,
            message_sender,
            player_repo=player_repo,
            map_manager=map_manager,
            broadcast_service=broadcast_service,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert - debe dropear solo 50
        player_repo.update_gold.assert_called_once_with(1, 0)
        message_sender.send_console_msg.assert_called_with("Tiraste 50 monedas de oro al suelo.")

    async def test_drop_gold_zero_quantity(self) -> None:
        """Test de drop con cantidad cero."""
        # Setup
        message_sender = MagicMock()
        message_sender.send_console_msg = AsyncMock()

        player_repo = MagicMock(spec=PlayerRepository)
        player_repo.get_stats = AsyncMock(return_value={"gold": 1000})
        player_repo.get_position = AsyncMock(return_value={"map": 1, "x": 50, "y": 50})

        map_manager = MagicMock(spec=MapManager)

        # Packet: DROP + slot=1 + quantity=0
        data = bytes([0x10, 0x01, 0x00, 0x00])

        session_data = {"user_id": 1}

        task = TaskDrop(
            data,
            message_sender,
            player_repo=player_repo,
            map_manager=map_manager,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert - El validador da un mensaje más descriptivo
        message_sender.send_console_msg.assert_called_once()
        call_args = message_sender.send_console_msg.call_args[0][0]
        assert "Cantidad inválida" in call_args
        player_repo.update_gold.assert_not_called()

    async def test_drop_gold_no_gold_available(self) -> None:
        """Test de drop cuando no tiene oro."""
        # Setup
        message_sender = MagicMock()
        message_sender.send_console_msg = AsyncMock()

        player_repo = MagicMock(spec=PlayerRepository)
        player_repo.get_stats = AsyncMock(return_value={"gold": 0})
        player_repo.get_position = AsyncMock(return_value={"map": 1, "x": 50, "y": 50})

        map_manager = MagicMock(spec=MapManager)

        # Packet: DROP + slot=1 + quantity=100
        data = bytes([0x10, 0x01, 0x64, 0x00])

        session_data = {"user_id": 1}

        task = TaskDrop(
            data,
            message_sender,
            player_repo=player_repo,
            map_manager=map_manager,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert
        message_sender.send_console_msg.assert_called_with("No tienes oro para tirar.")
        player_repo.update_gold.assert_not_called()

    async def test_drop_without_session(self) -> None:
        """Test de drop sin sesión activa."""
        # Setup
        message_sender = MagicMock()
        player_repo = MagicMock(spec=PlayerRepository)

        data = bytes([0x10, 0x01, 0x64, 0x00])
        session_data = {}  # Sin user_id

        task = TaskDrop(data, message_sender, player_repo=player_repo, session_data=session_data)

        # Execute
        await task.execute()

        # Assert
        player_repo.get_stats.assert_not_called()

    async def test_drop_invalid_packet_size(self) -> None:
        """Test con packet de tamaño inválido."""
        # Setup
        message_sender = MagicMock()
        message_sender.send_console_msg = AsyncMock()
        player_repo = MagicMock(spec=PlayerRepository)

        # Packet muy corto
        data = bytes([0x10, 0x01])  # Falta quantity

        session_data = {"user_id": 1}

        task = TaskDrop(data, message_sender, player_repo=player_repo, session_data=session_data)

        # Execute
        await task.execute()

        # Debe enviar mensaje de error
        message_sender.send_console_msg.assert_called_once()

    async def test_drop_without_dependencies(self) -> None:
        """Test sin dependencias necesarias."""
        # Setup
        message_sender = MagicMock()
        message_sender.send_console_msg = AsyncMock()

        data = bytes([0x10, 0x01, 0x64, 0x00])
        session_data = {"user_id": 1}

        task = TaskDrop(
            data,
            message_sender,
            player_repo=None,  # Sin dependencias
            map_manager=None,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert - no debe crashear

    async def test_drop_stats_not_found(self) -> None:
        """Test cuando no se encuentran stats del jugador."""
        # Setup
        message_sender = MagicMock()

        player_repo = MagicMock(spec=PlayerRepository)
        player_repo.get_stats = AsyncMock(return_value=None)  # No encontrado

        map_manager = MagicMock(spec=MapManager)

        data = bytes([0x10, 0x01, 0x64, 0x00])
        session_data = {"user_id": 1}

        task = TaskDrop(
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

    async def test_drop_position_not_found(self) -> None:
        """Test cuando no se encuentra la posición del jugador."""
        # Setup
        message_sender = MagicMock()

        player_repo = MagicMock(spec=PlayerRepository)
        player_repo.get_stats = AsyncMock(return_value={"gold": 1000})
        player_repo.get_position = AsyncMock(return_value=None)  # No encontrado

        map_manager = MagicMock(spec=MapManager)

        data = bytes([0x10, 0x01, 0x64, 0x00])
        session_data = {"user_id": 1}

        task = TaskDrop(
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
