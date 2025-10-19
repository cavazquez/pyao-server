"""Tests para TaskEquipItem."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.task_equip_item import TaskEquipItem


@pytest.mark.asyncio
class TestTaskEquipItem:
    """Tests para TaskEquipItem."""

    async def test_equip_item_success(self) -> None:
        """Test de equipar item exitoso."""
        # Setup
        message_sender = MagicMock()

        player_repo = MagicMock()
        player_repo.redis = MagicMock()

        equipment_repo = MagicMock()

        # Packet: EQUIP_ITEM + slot=1
        data = bytes([0x15, 0x01])

        session_data = {"user_id": 1}

        # Mock de los servicios
        with (
            patch("src.task_equip_item.InventoryRepository"),
            patch("src.task_equip_item.EquipmentService") as mock_equip_service,
            patch("src.task_equip_item.PlayerService") as mock_player_service,
        ):
            mock_equip_service_instance = MagicMock()
            mock_equip_service_instance.toggle_equip_item = AsyncMock(return_value=True)
            mock_equip_service.return_value = mock_equip_service_instance

            mock_player_service_instance = MagicMock()
            mock_player_service_instance.send_inventory = AsyncMock()
            mock_player_service.return_value = mock_player_service_instance

            task = TaskEquipItem(
                data,
                message_sender,
                player_repo=player_repo,
                session_data=session_data,
                equipment_repo=equipment_repo,
            )

            # Execute
            await task.execute()

            # Assert
            mock_equip_service_instance.toggle_equip_item.assert_called_once_with(
                1, 1, message_sender
            )
            mock_player_service_instance.send_inventory.assert_called_once_with(1, equipment_repo)

    async def test_equip_item_failure(self) -> None:
        """Test cuando falla equipar el item."""
        # Setup
        message_sender = MagicMock()

        player_repo = MagicMock()
        player_repo.redis = MagicMock()

        equipment_repo = MagicMock()

        data = bytes([0x15, 0x01])
        session_data = {"user_id": 1}

        with (
            patch("src.task_equip_item.InventoryRepository"),
            patch("src.task_equip_item.EquipmentService") as mock_equip_service,
            patch("src.task_equip_item.PlayerService") as mock_player_service,
        ):
            mock_equip_service_instance = MagicMock()
            mock_equip_service_instance.toggle_equip_item = AsyncMock(return_value=False)
            mock_equip_service.return_value = mock_equip_service_instance

            mock_player_service_instance = MagicMock()
            mock_player_service_instance.send_inventory = AsyncMock()
            mock_player_service.return_value = mock_player_service_instance

            task = TaskEquipItem(
                data,
                message_sender,
                player_repo=player_repo,
                session_data=session_data,
                equipment_repo=equipment_repo,
            )

            # Execute
            await task.execute()

            # Assert - no debe enviar inventario si falla
            mock_player_service_instance.send_inventory.assert_not_called()

    async def test_equip_item_without_session(self) -> None:
        """Test sin sesión activa."""
        # Setup
        message_sender = MagicMock()
        player_repo = MagicMock()
        equipment_repo = MagicMock()

        data = bytes([0x15, 0x01])
        session_data = {}  # Sin user_id

        task = TaskEquipItem(
            data,
            message_sender,
            player_repo=player_repo,
            session_data=session_data,
            equipment_repo=equipment_repo,
        )

        # Execute
        await task.execute()

        # Assert - no debe hacer nada

    async def test_equip_item_invalid_packet_size(self) -> None:
        """Test con packet de tamaño inválido."""
        # Setup
        message_sender = MagicMock()
        player_repo = MagicMock()
        equipment_repo = MagicMock()

        # Packet muy corto
        data = bytes([0x15])  # Falta slot

        session_data = {"user_id": 1}

        task = TaskEquipItem(
            data,
            message_sender,
            player_repo=player_repo,
            session_data=session_data,
            equipment_repo=equipment_repo,
        )

        # Execute
        await task.execute()

        # Assert - no debe crashear

    async def test_equip_item_without_dependencies(self) -> None:
        """Test sin dependencias necesarias."""
        # Setup
        message_sender = MagicMock()

        data = bytes([0x15, 0x01])
        session_data = {"user_id": 1}

        task = TaskEquipItem(
            data,
            message_sender,
            player_repo=None,  # Sin dependencias
            session_data=session_data,
            equipment_repo=None,
        )

        # Execute
        await task.execute()

        # Assert - no debe crashear
