"""Tests para TaskInventoryClick."""

import struct
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.message_sender import MessageSender
from src.task_inventory_click import TaskInventoryClick


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

        # Mock del inventario con un item
        with patch("src.task_inventory_click.InventoryRepository") as mock_inv_repo:
            mock_inv_instance = mock_inv_repo.return_value
            mock_inv_instance.get_slot = AsyncMock(return_value=(1, 5))  # Item 1, cantidad 5

            # Crear packet: PacketID (0x1E) + Slot (1)
            data = struct.pack("BB", 0x1E, 1)

            task = TaskInventoryClick(
                data,
                message_sender,
                slot=1,
                player_repo=mock_player_repo,
                session_data=session_data,
            )
            await task.execute()

            # Verificar que se envió el paquete de actualización de inventario
            sent_data = message_sender.connection.sent_data
            assert len(sent_data) > 0

            # El primer byte debe ser el PacketID de CHANGE_INVENTORY_SLOT
            assert sent_data[0] == 0x2F  # 47 en decimal

    @pytest.mark.asyncio
    async def test_inventory_click_empty_slot(self, message_sender, mock_player_repo):
        """Verifica que el click en un slot vacío funcione."""
        session_data = {"user_id": 1}

        # Mock del inventario con slot vacío
        with patch("src.task_inventory_click.InventoryRepository") as mock_inv_repo:
            mock_inv_instance = mock_inv_repo.return_value
            mock_inv_instance.get_slot = AsyncMock(return_value=None)

            # Crear packet: PacketID (0x1E) + Slot (5) - slot vacío
            data = struct.pack("BB", 0x1E, 5)

            task = TaskInventoryClick(
                data,
                message_sender,
                slot=5,
                player_repo=mock_player_repo,
                session_data=session_data,
            )
            await task.execute()

            # Verificar que se envió un paquete
            sent_data = message_sender.connection.sent_data
            assert len(sent_data) > 0

    @pytest.mark.asyncio
    async def test_inventory_click_no_session(self, message_sender, mock_player_repo):
        """Verifica que falle sin sesión."""
        # Sin session_data
        data = struct.pack("BB", 0x1E, 1)

        task = TaskInventoryClick(
            data, message_sender, slot=1, player_repo=mock_player_repo, session_data=None
        )
        await task.execute()

        # No debería enviar nada
        sent_data = message_sender.connection.sent_data
        assert len(sent_data) == 0

    @pytest.mark.asyncio
    async def test_inventory_click_no_user_id(self, message_sender, mock_player_repo):
        """Verifica que falle sin user_id en sesión."""
        session_data = {}  # Sin user_id
        data = struct.pack("BB", 0x1E, 1)

        task = TaskInventoryClick(
            data, message_sender, slot=1, player_repo=mock_player_repo, session_data=session_data
        )
        await task.execute()

        # No debería enviar actualización de inventario
        sent_data = message_sender.connection.sent_data
        assert len(sent_data) == 0

    @pytest.mark.asyncio
    async def test_inventory_click_no_player_repo(self, message_sender):
        """Verifica que falle sin player_repo."""
        session_data = {"user_id": 1}
        data = struct.pack("BB", 0x1E, 1)

        task = TaskInventoryClick(
            data, message_sender, slot=1, player_repo=None, session_data=session_data
        )
        await task.execute()

        # No debería enviar nada
        sent_data = message_sender.connection.sent_data
        assert len(sent_data) == 0

    @pytest.mark.asyncio
    async def test_inventory_click_invalid_packet_size(self, message_sender, mock_player_repo):
        """Verifica que falle con packet inválido."""
        session_data = {"user_id": 1}
        data = struct.pack("B", 0x1E)  # Solo 1 byte, faltan datos

        task = TaskInventoryClick(
            data, message_sender, slot=1, player_repo=mock_player_repo, session_data=session_data
        )
        await task.execute()

        # No debería enviar nada
        sent_data = message_sender.connection.sent_data
        assert len(sent_data) == 0

    @pytest.mark.asyncio
    async def test_inventory_click_item_not_in_catalog(self, message_sender, mock_player_repo):
        """Verifica el comportamiento con un item no existente en el catálogo."""
        session_data = {"user_id": 1}

        # Mock del inventario con un item que no existe en el catálogo
        with patch("src.task_inventory_click.InventoryRepository") as mock_inv_repo:
            mock_inv_instance = mock_inv_repo.return_value
            mock_inv_instance.get_slot = AsyncMock(return_value=(99999, 1))  # Item inexistente

            # Click en el slot
            data = struct.pack("BB", 0x1E, 1)
            task = TaskInventoryClick(
                data,
                message_sender,
                slot=1,
                player_repo=mock_player_repo,
                session_data=session_data,
            )
            await task.execute()

            # Debería enviar un mensaje de error
            sent_data = message_sender.connection.sent_data
            assert len(sent_data) > 0
            # El mensaje debería ser un CONSOLE_MSG (0x18)
            assert sent_data[0] == 0x18
