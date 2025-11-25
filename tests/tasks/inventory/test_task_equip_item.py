"""Tests para TaskEquipItem."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.commands.base import CommandResult
from src.commands.equip_item_command import EquipItemCommand
from src.tasks.inventory.task_equip_item import TaskEquipItem


def create_mock_equip_item_handler(
    player_repo: MagicMock | None = None,
    equipment_repo: MagicMock | None = None,
    message_sender: MagicMock | None = None,
) -> MagicMock:
    """Crea un mock de EquipItemCommandHandler con las dependencias especificadas."""
    handler = MagicMock()
    handler.player_repo = player_repo or MagicMock()
    handler.equipment_repo = equipment_repo or MagicMock()
    handler.message_sender = message_sender or MagicMock()
    handler.handle = AsyncMock()
    return handler


@pytest.mark.asyncio
class TestTaskEquipItem:
    """Tests para TaskEquipItem."""

    async def test_equip_item_success(self) -> None:
        """Test de equipar item exitoso."""
        # Setup
        message_sender = AsyncMock()

        equip_item_handler = create_mock_equip_item_handler(message_sender=message_sender)
        equip_item_handler.handle.return_value = CommandResult.ok(data={"slot": 1, "success": True})

        # Packet: EQUIP_ITEM (19) + slot=1 + padding
        data = bytes([0x13, 0x01, 0x00])
        session_data = {"user_id": 1}

        task = TaskEquipItem(
            data,
            message_sender,
            equip_item_handler=equip_item_handler,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert
        equip_item_handler.handle.assert_called_once()
        call_args = equip_item_handler.handle.call_args[0][0]
        assert isinstance(call_args, EquipItemCommand)
        assert call_args.user_id == 1
        assert call_args.slot == 1

    async def test_equip_item_failure(self) -> None:
        """Test cuando falla equipar el item."""
        # Setup
        message_sender = AsyncMock()

        equip_item_handler = create_mock_equip_item_handler(message_sender=message_sender)
        equip_item_handler.handle.return_value = CommandResult.error(
            "No se pudo equipar/desequipar el item"
        )

        data = bytes([0x13, 0x01, 0x00])
        session_data = {"user_id": 1}

        task = TaskEquipItem(
            data,
            message_sender,
            equip_item_handler=equip_item_handler,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert
        equip_item_handler.handle.assert_called_once()

    async def test_equip_item_without_session(self) -> None:
        """Test sin sesión activa."""
        # Setup
        message_sender = AsyncMock()
        equip_item_handler = create_mock_equip_item_handler(message_sender=message_sender)

        data = bytes([0x13, 0x01, 0x00])
        session_data = {}  # Sin user_id

        task = TaskEquipItem(
            data,
            message_sender,
            equip_item_handler=equip_item_handler,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert - no debe hacer nada
        equip_item_handler.handle.assert_not_called()

    async def test_equip_item_invalid_packet_size(self) -> None:
        """Test con packet de tamaño inválido."""
        # Setup
        message_sender = AsyncMock()
        message_sender.send_console_msg = AsyncMock()
        equip_item_handler = create_mock_equip_item_handler(message_sender=message_sender)

        # Packet muy corto
        data = bytes([0x13])  # Falta slot
        session_data = {"user_id": 1}

        task = TaskEquipItem(
            data,
            message_sender,
            equip_item_handler=equip_item_handler,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert - no debe crashear, debe enviar mensaje de error
        equip_item_handler.handle.assert_not_called()

    async def test_equip_item_without_handler(self) -> None:
        """Test sin handler."""
        # Setup
        message_sender = AsyncMock()

        data = bytes([0x13, 0x01, 0x00])
        session_data = {"user_id": 1}

        task = TaskEquipItem(
            data,
            message_sender,
            equip_item_handler=None,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert - no debe crashear
