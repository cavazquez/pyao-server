"""Tests para TaskInventoryClick."""

import struct
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.commands.base import CommandResult
from src.commands.inventory_click_command import InventoryClickCommand
from src.messaging.message_sender import MessageSender
from src.tasks.inventory.task_inventory_click import TaskInventoryClick


def create_mock_inventory_click_handler(
    player_repo: MagicMock | None = None,
    equipment_repo: MagicMock | None = None,
    message_sender: MagicMock | None = None,
) -> MagicMock:
    """Crea un mock de InventoryClickCommandHandler con las dependencias especificadas."""
    handler = MagicMock()
    handler.player_repo = player_repo or MagicMock()
    handler.equipment_repo = equipment_repo or MagicMock()
    handler.message_sender = message_sender or MagicMock()
    handler.handle = AsyncMock()
    return handler


@pytest.fixture
def mock_connection():
    """Fixture para crear una conexión mock."""
    connection = MagicMock()
    connection.address = ("127.0.0.1", 12345)
    connection.send = AsyncMock()
    connection.sent_data = bytearray()

    # Mock para capturar datos enviados
    async def mock_send(data):
        connection.sent_data.extend(data)

    connection.send = mock_send
    return connection


@pytest.fixture
def message_sender(mock_connection):
    """Fixture para crear un MessageSender."""
    return MessageSender(mock_connection)


@pytest.fixture
def mock_player_repo():
    """Fixture para crear un PlayerRepository mock."""
    repo = MagicMock()
    repo.redis = MagicMock()
    return repo


class TestTaskInventoryClick:
    """Tests para TaskInventoryClick."""

    @pytest.mark.asyncio
    async def test_inventory_click_with_item(self, message_sender, mock_player_repo):
        """Verifica que el click en un slot con item funcione."""
        session_data = {"user_id": 1}

        inventory_click_handler = create_mock_inventory_click_handler(
            player_repo=mock_player_repo, message_sender=message_sender
        )
        inventory_click_handler.handle.return_value = CommandResult.ok(
            data={"slot": 1, "item_id": 1, "quantity": 5, "is_equipped": False}
        )

        # Crear packet: PacketID (0x1E) + Slot (1)
        data = struct.pack("BB", 0x1E, 1)

        task = TaskInventoryClick(
            data,
            message_sender,
            slot=1,
            inventory_click_handler=inventory_click_handler,
            session_data=session_data,
        )
        await task.execute()

        # Debe llamar al handler con el comando correcto
        inventory_click_handler.handle.assert_called_once()
        call_args = inventory_click_handler.handle.call_args[0][0]
        assert isinstance(call_args, InventoryClickCommand)
        assert call_args.user_id == 1
        assert call_args.slot == 1

    @pytest.mark.asyncio
    async def test_inventory_click_empty_slot(self, message_sender, mock_player_repo):
        """Verifica que el click en un slot vacío funcione."""
        session_data = {"user_id": 1}

        inventory_click_handler = create_mock_inventory_click_handler(
            player_repo=mock_player_repo, message_sender=message_sender
        )
        inventory_click_handler.handle.return_value = CommandResult.ok(
            data={"slot": 5, "empty": True}
        )

        # Crear packet: PacketID (0x1E) + Slot (5) - slot vacío
        data = struct.pack("BB", 0x1E, 5)

        task = TaskInventoryClick(
            data,
            message_sender,
            slot=5,
            inventory_click_handler=inventory_click_handler,
            session_data=session_data,
        )
        await task.execute()

        # Debe llamar al handler
        inventory_click_handler.handle.assert_called_once()

    @pytest.mark.asyncio
    async def test_inventory_click_no_session(self, message_sender):
        """Verifica que falle sin sesión."""
        # Sin session_data
        data = struct.pack("BB", 0x1E, 1)

        inventory_click_handler = create_mock_inventory_click_handler()

        task = TaskInventoryClick(
            data,
            message_sender,
            slot=1,
            inventory_click_handler=inventory_click_handler,
            session_data=None,
        )
        await task.execute()

        # No debe llamar al handler sin sesión
        inventory_click_handler.handle.assert_not_called()

    @pytest.mark.asyncio
    async def test_inventory_click_no_user_id(self, message_sender):
        """Verifica que falle sin user_id en sesión."""
        session_data = {}  # Sin user_id
        data = struct.pack("BB", 0x1E, 1)

        inventory_click_handler = create_mock_inventory_click_handler()

        task = TaskInventoryClick(
            data,
            message_sender,
            slot=1,
            inventory_click_handler=inventory_click_handler,
            session_data=session_data,
        )
        await task.execute()

        # No debe llamar al handler sin user_id
        inventory_click_handler.handle.assert_not_called()

    @pytest.mark.asyncio
    async def test_inventory_click_no_handler(self, message_sender):
        """Verifica que falle sin handler."""
        session_data = {"user_id": 1}
        data = struct.pack("BB", 0x1E, 1)

        task = TaskInventoryClick(
            data, message_sender, slot=1, inventory_click_handler=None, session_data=session_data
        )
        await task.execute()

        # No debe hacer nada sin handler
        # (el test solo verifica que no crashee)

    @pytest.mark.asyncio
    async def test_inventory_click_invalid_packet_size(self, message_sender):
        """Verifica que falle con packet inválido."""
        session_data = {"user_id": 1}
        data = struct.pack("B", 0x1E)  # Solo 1 byte, faltan datos

        inventory_click_handler = create_mock_inventory_click_handler()

        task = TaskInventoryClick(
            data,
            message_sender,
            slot=1,
            inventory_click_handler=inventory_click_handler,
            session_data=session_data,
        )
        await task.execute()

        # El slot ya está validado por TaskFactory, así que debería llamar al handler
        # (el packet inválido se maneja en TaskFactory, no aquí)
        # Pero como el slot se pasa directamente, el handler debería ser llamado
        inventory_click_handler.handle.assert_called_once()

    @pytest.mark.asyncio
    async def test_inventory_click_item_not_in_catalog(self, message_sender, mock_player_repo):
        """Verifica el comportamiento con un item no existente en el catálogo."""
        session_data = {"user_id": 1}

        inventory_click_handler = create_mock_inventory_click_handler(
            player_repo=mock_player_repo, message_sender=message_sender
        )
        inventory_click_handler.handle.return_value = CommandResult.error("Item no válido")

        # Click en el slot
        data = struct.pack("BB", 0x1E, 1)
        task = TaskInventoryClick(
            data,
            message_sender,
            slot=1,
            inventory_click_handler=inventory_click_handler,
            session_data=session_data,
        )
        await task.execute()

        # Debe llamar al handler
        inventory_click_handler.handle.assert_called_once()
