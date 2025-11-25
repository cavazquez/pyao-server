"""Tests para TaskDrop."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.commands.base import CommandResult
from src.commands.drop_command import DropCommand
from src.tasks.inventory.task_drop import TaskDrop


def create_mock_drop_handler(
    player_repo: MagicMock | None = None,
    inventory_repo: MagicMock | None = None,
    map_manager: MagicMock | None = None,
    broadcast_service: MagicMock | None = None,
    message_sender: MagicMock | None = None,
) -> MagicMock:
    """Crea un mock de DropCommandHandler con las dependencias especificadas."""
    handler = MagicMock()
    handler.player_repo = player_repo or MagicMock()
    handler.inventory_repo = inventory_repo
    handler.map_manager = map_manager or MagicMock()
    handler.broadcast_service = broadcast_service
    handler.message_sender = message_sender or MagicMock()
    handler.handle = AsyncMock()
    return handler


@pytest.mark.asyncio
class TestTaskDrop:
    """Tests para TaskDrop."""

    async def test_drop_gold_success(self) -> None:
        """Test de drop de oro exitoso."""
        # Setup
        message_sender = MagicMock()
        message_sender.send_console_msg = AsyncMock()
        message_sender.send_update_user_stats = AsyncMock()

        drop_handler = create_mock_drop_handler(message_sender=message_sender)
        drop_handler.handle.return_value = CommandResult.ok(
            data={"item_id": 12, "quantity": 100, "type": "gold"}
        )

        # Packet: DROP + slot=1 + quantity=100
        data = bytes([0x10, 0x01, 0x64, 0x00])  # 100 en little-endian
        session_data = {"user_id": 1}

        task = TaskDrop(
            data,
            message_sender,
            drop_handler=drop_handler,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert
        drop_handler.handle.assert_called_once()
        call_args = drop_handler.handle.call_args[0][0]
        assert isinstance(call_args, DropCommand)
        assert call_args.user_id == 1
        assert call_args.slot == 1
        assert call_args.quantity == 100

    async def test_drop_gold_more_than_available(self) -> None:
        """Test de drop de más oro del que se tiene."""
        # Setup
        message_sender = MagicMock()
        message_sender.send_console_msg = AsyncMock()
        message_sender.send_update_user_stats = AsyncMock()

        drop_handler = create_mock_drop_handler(message_sender=message_sender)
        drop_handler.handle.return_value = CommandResult.ok(
            data={"item_id": 12, "quantity": 50, "type": "gold"}
        )

        # Packet: DROP + slot=1 + quantity=100 (pero solo tiene 50)
        data = bytes([0x10, 0x01, 0x64, 0x00])
        session_data = {"user_id": 1}

        task = TaskDrop(
            data,
            message_sender,
            drop_handler=drop_handler,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert - debe dropear solo 50 (la lógica está en el handler)
        drop_handler.handle.assert_called_once()

    async def test_drop_gold_zero_quantity(self) -> None:
        """Test de drop con cantidad cero."""
        # Setup
        message_sender = MagicMock()
        message_sender.send_console_msg = AsyncMock()

        drop_handler = create_mock_drop_handler(message_sender=message_sender)

        # Packet: DROP + slot=1 + quantity=0
        data = bytes([0x10, 0x01, 0x00, 0x00])
        session_data = {"user_id": 1}

        task = TaskDrop(
            data,
            message_sender,
            drop_handler=drop_handler,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert - El validador da un mensaje más descriptivo
        message_sender.send_console_msg.assert_called_once()
        call_args = message_sender.send_console_msg.call_args[0][0]
        assert "Cantidad inválida" in call_args
        drop_handler.handle.assert_not_called()

    async def test_drop_gold_no_gold_available(self) -> None:
        """Test de drop cuando no tiene oro."""
        # Setup
        message_sender = MagicMock()
        message_sender.send_console_msg = AsyncMock()

        drop_handler = create_mock_drop_handler(message_sender=message_sender)
        drop_handler.handle.return_value = CommandResult.error("No tienes oro para tirar")

        # Packet: DROP + slot=1 + quantity=100
        data = bytes([0x10, 0x01, 0x64, 0x00])
        session_data = {"user_id": 1}

        task = TaskDrop(
            data,
            message_sender,
            drop_handler=drop_handler,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert
        drop_handler.handle.assert_called_once()

    async def test_drop_without_session(self) -> None:
        """Test de drop sin sesión activa."""
        # Setup
        message_sender = MagicMock()
        drop_handler = create_mock_drop_handler(message_sender=message_sender)

        data = bytes([0x10, 0x01, 0x64, 0x00])
        session_data = {}  # Sin user_id

        task = TaskDrop(data, message_sender, drop_handler=drop_handler, session_data=session_data)

        # Execute
        await task.execute()

        # Assert
        drop_handler.handle.assert_not_called()

    async def test_drop_invalid_packet_size(self) -> None:
        """Test con packet de tamaño inválido."""
        # Setup
        message_sender = MagicMock()
        message_sender.send_console_msg = AsyncMock()
        drop_handler = create_mock_drop_handler(message_sender=message_sender)

        # Packet muy corto
        data = bytes([0x10, 0x01])  # Falta quantity
        session_data = {"user_id": 1}

        task = TaskDrop(data, message_sender, drop_handler=drop_handler, session_data=session_data)

        # Execute
        await task.execute()

        # Debe enviar mensaje de error
        message_sender.send_console_msg.assert_called_once()
        drop_handler.handle.assert_not_called()

    async def test_drop_without_handler(self) -> None:
        """Test sin handler."""
        # Setup
        message_sender = MagicMock()
        message_sender.send_console_msg = AsyncMock()

        data = bytes([0x10, 0x01, 0x64, 0x00])
        session_data = {"user_id": 1}

        task = TaskDrop(
            data,
            message_sender,
            drop_handler=None,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert - no debe crashear

    async def test_drop_stats_not_found(self) -> None:
        """Test cuando no se encuentran stats del jugador."""
        # Setup
        message_sender = MagicMock()

        drop_handler = create_mock_drop_handler(message_sender=message_sender)
        drop_handler.handle.return_value = CommandResult.error(
            "No se pudieron obtener los stats del jugador"
        )

        data = bytes([0x10, 0x01, 0x64, 0x00])
        session_data = {"user_id": 1}

        task = TaskDrop(
            data,
            message_sender,
            drop_handler=drop_handler,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert
        drop_handler.handle.assert_called_once()

    async def test_drop_position_not_found(self) -> None:
        """Test cuando no se encuentra la posición del jugador."""
        # Setup
        message_sender = MagicMock()

        drop_handler = create_mock_drop_handler(message_sender=message_sender)
        drop_handler.handle.return_value = CommandResult.error(
            "No se pudo obtener la posición del jugador"
        )

        data = bytes([0x10, 0x01, 0x64, 0x00])
        session_data = {"user_id": 1}

        task = TaskDrop(
            data,
            message_sender,
            drop_handler=drop_handler,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert
        drop_handler.handle.assert_called_once()
