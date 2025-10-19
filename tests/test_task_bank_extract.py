"""Tests para TaskBankExtract."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.bank_repository import BankItem, BankRepository
from src.inventory_repository import InventoryRepository
from src.player_repository import PlayerRepository
from src.task_bank_extract import TaskBankExtract


@pytest.mark.asyncio
class TestTaskBankExtract:
    """Tests para TaskBankExtract."""

    async def test_extract_success(self) -> None:
        """Test de extracción exitosa."""
        # Setup
        message_sender = MagicMock()
        message_sender.send_console_msg = AsyncMock()
        message_sender.send_change_inventory_slot = AsyncMock()
        message_sender.send_change_bank_slot = AsyncMock()

        bank_repo = MagicMock(spec=BankRepository)
        bank_repo.get_item = AsyncMock(return_value=BankItem(slot=1, item_id=10, quantity=10))
        bank_repo.extract_item = AsyncMock(return_value=True)

        inventory_repo = MagicMock(spec=InventoryRepository)
        inventory_repo.add_item = AsyncMock(return_value=[(1, 5)])  # Slot 1, cantidad 5

        player_repo = MagicMock(spec=PlayerRepository)

        # Packet: BANK_EXTRACT_ITEM + slot=1 + quantity=5
        data = bytes([41, 1, 5, 0])  # quantity en little-endian

        session_data = {"user_id": 1}

        task = TaskBankExtract(
            data,
            message_sender,
            bank_repo=bank_repo,
            inventory_repo=inventory_repo,
            player_repo=player_repo,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert
        bank_repo.get_item.assert_called_once_with(1, 1)
        bank_repo.extract_item.assert_called_once_with(1, 1, 5)
        inventory_repo.add_item.assert_called_once_with(1, 10, 5)
        message_sender.send_change_bank_slot.assert_called_once()
        message_sender.send_change_inventory_slot.assert_called_once()
        message_sender.send_console_msg.assert_called()

    async def test_extract_without_session(self) -> None:
        """Test de extracción sin sesión activa."""
        # Setup
        message_sender = MagicMock()
        bank_repo = MagicMock(spec=BankRepository)
        inventory_repo = MagicMock(spec=InventoryRepository)
        player_repo = MagicMock(spec=PlayerRepository)

        data = bytes([41, 1, 1, 0])
        session_data = {}  # Sin user_id

        task = TaskBankExtract(
            data,
            message_sender,
            bank_repo=bank_repo,
            inventory_repo=inventory_repo,
            player_repo=player_repo,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert - no debe hacer nada
        bank_repo.extract_item.assert_not_called()

    async def test_extract_invalid_quantity(self) -> None:
        """Test de extracción con cantidad inválida."""
        # Setup
        message_sender = MagicMock()
        message_sender.send_console_msg = AsyncMock()

        bank_repo = MagicMock(spec=BankRepository)
        inventory_repo = MagicMock(spec=InventoryRepository)
        player_repo = MagicMock(spec=PlayerRepository)

        # Packet con cantidad 0
        data = bytes([41, 1, 0, 0])

        session_data = {"user_id": 1}

        task = TaskBankExtract(
            data,
            message_sender,
            bank_repo=bank_repo,
            inventory_repo=inventory_repo,
            player_repo=player_repo,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert
        message_sender.send_console_msg.assert_called_with("Cantidad inválida")
        bank_repo.extract_item.assert_not_called()

    async def test_extract_empty_slot(self) -> None:
        """Test de extracción desde slot vacío."""
        # Setup
        message_sender = MagicMock()
        message_sender.send_console_msg = AsyncMock()

        bank_repo = MagicMock(spec=BankRepository)
        bank_repo.get_item = AsyncMock(return_value=None)  # Slot vacío

        inventory_repo = MagicMock(spec=InventoryRepository)
        player_repo = MagicMock(spec=PlayerRepository)

        data = bytes([41, 1, 5, 0])
        session_data = {"user_id": 1}

        task = TaskBankExtract(
            data,
            message_sender,
            bank_repo=bank_repo,
            inventory_repo=inventory_repo,
            player_repo=player_repo,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert
        message_sender.send_console_msg.assert_called_with(
            "No hay ningún item en ese slot del banco"
        )
        bank_repo.extract_item.assert_not_called()

    async def test_extract_insufficient_quantity(self) -> None:
        """Test de extracción con cantidad insuficiente."""
        # Setup
        message_sender = MagicMock()
        message_sender.send_console_msg = AsyncMock()

        bank_repo = MagicMock(spec=BankRepository)
        bank_repo.get_item = AsyncMock(
            return_value=BankItem(slot=1, item_id=10, quantity=3)  # Solo 3 items
        )

        inventory_repo = MagicMock(spec=InventoryRepository)
        player_repo = MagicMock(spec=PlayerRepository)

        # Intentar extraer 5 items
        data = bytes([41, 1, 5, 0])
        session_data = {"user_id": 1}

        task = TaskBankExtract(
            data,
            message_sender,
            bank_repo=bank_repo,
            inventory_repo=inventory_repo,
            player_repo=player_repo,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert
        message_sender.send_console_msg.assert_called_with(
            "Solo tienes 3 items en ese slot del banco"
        )
        bank_repo.extract_item.assert_not_called()

    async def test_extract_fails(self) -> None:
        """Test cuando falla la extracción del banco."""
        # Setup
        message_sender = MagicMock()
        message_sender.send_console_msg = AsyncMock()

        bank_repo = MagicMock(spec=BankRepository)
        bank_repo.get_item = AsyncMock(return_value=BankItem(slot=1, item_id=10, quantity=5))
        bank_repo.extract_item = AsyncMock(return_value=False)  # Falla

        inventory_repo = MagicMock(spec=InventoryRepository)
        player_repo = MagicMock(spec=PlayerRepository)

        data = bytes([41, 1, 5, 0])
        session_data = {"user_id": 1}

        task = TaskBankExtract(
            data,
            message_sender,
            bank_repo=bank_repo,
            inventory_repo=inventory_repo,
            player_repo=player_repo,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert
        message_sender.send_console_msg.assert_called_with("Error al extraer del banco")
        inventory_repo.add_item.assert_not_called()

    async def test_extract_inventory_full(self) -> None:
        """Test de extracción cuando el inventario está lleno."""
        # Setup
        message_sender = MagicMock()
        message_sender.send_console_msg = AsyncMock()

        bank_repo = MagicMock(spec=BankRepository)
        bank_repo.get_item = AsyncMock(return_value=BankItem(slot=1, item_id=10, quantity=5))
        bank_repo.extract_item = AsyncMock(return_value=True)
        bank_repo.deposit_item = AsyncMock()  # Para rollback

        inventory_repo = MagicMock(spec=InventoryRepository)
        inventory_repo.add_item = AsyncMock(return_value=[])  # No hay espacio

        player_repo = MagicMock(spec=PlayerRepository)

        data = bytes([41, 1, 5, 0])
        session_data = {"user_id": 1}

        task = TaskBankExtract(
            data,
            message_sender,
            bank_repo=bank_repo,
            inventory_repo=inventory_repo,
            player_repo=player_repo,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert
        message_sender.send_console_msg.assert_called_with("No tienes espacio en el inventario")
        # Debe hacer rollback
        bank_repo.deposit_item.assert_called_once_with(1, 10, 5)
        message_sender.send_change_bank_slot.assert_not_called()

    async def test_extract_invalid_packet_size(self) -> None:
        """Test con packet de tamaño inválido."""
        # Setup
        message_sender = MagicMock()
        bank_repo = MagicMock(spec=BankRepository)
        inventory_repo = MagicMock(spec=InventoryRepository)
        player_repo = MagicMock(spec=PlayerRepository)

        # Packet muy corto
        data = bytes([41, 1])  # Falta quantity

        session_data = {"user_id": 1}

        task = TaskBankExtract(
            data,
            message_sender,
            bank_repo=bank_repo,
            inventory_repo=inventory_repo,
            player_repo=player_repo,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert - no debe crashear
        bank_repo.extract_item.assert_not_called()

    async def test_extract_without_dependencies(self) -> None:
        """Test sin dependencias disponibles."""
        # Setup
        message_sender = MagicMock()
        message_sender.send_console_msg = AsyncMock()

        data = bytes([41, 1, 5, 0])
        session_data = {"user_id": 1}

        task = TaskBankExtract(
            data,
            message_sender,
            bank_repo=None,  # Sin dependencias
            inventory_repo=None,
            player_repo=None,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert
        message_sender.send_console_msg.assert_called_with("Error al extraer del banco")

    async def test_extract_multiple_slots(self) -> None:
        """Test de extracción que llena múltiples slots del inventario."""
        # Setup
        message_sender = MagicMock()
        message_sender.send_console_msg = AsyncMock()
        message_sender.send_change_inventory_slot = AsyncMock()
        message_sender.send_change_bank_slot = AsyncMock()

        bank_repo = MagicMock(spec=BankRepository)
        bank_repo.get_item = AsyncMock(return_value=BankItem(slot=1, item_id=10, quantity=10))
        bank_repo.extract_item = AsyncMock(return_value=True)

        inventory_repo = MagicMock(spec=InventoryRepository)
        # Simula que se llenaron 2 slots
        inventory_repo.add_item = AsyncMock(return_value=[(1, 5), (2, 5)])

        player_repo = MagicMock(spec=PlayerRepository)

        data = bytes([41, 1, 10, 0])
        session_data = {"user_id": 1}

        task = TaskBankExtract(
            data,
            message_sender,
            bank_repo=bank_repo,
            inventory_repo=inventory_repo,
            player_repo=player_repo,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert - debe enviar 2 actualizaciones de inventario
        assert message_sender.send_change_inventory_slot.call_count == 2
