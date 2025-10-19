"""Tests para TaskBankDeposit."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.bank_repository import BankItem, BankRepository
from src.inventory_repository import InventoryRepository
from src.player_repository import PlayerRepository
from src.task_bank_deposit import TaskBankDeposit


@pytest.mark.asyncio
class TestTaskBankDeposit:
    """Tests para TaskBankDeposit."""

    async def test_deposit_success(self) -> None:
        """Test de depósito exitoso."""
        # Setup
        message_sender = MagicMock()
        message_sender.send_console_msg = AsyncMock()
        message_sender.send_change_inventory_slot = AsyncMock()
        message_sender.send_change_bank_slot = AsyncMock()

        bank_repo = MagicMock(spec=BankRepository)
        bank_repo.deposit_item = AsyncMock(return_value=1)  # Slot 1
        bank_repo.get_item = AsyncMock(return_value=BankItem(slot=1, item_id=10, quantity=5))

        inventory_repo = MagicMock(spec=InventoryRepository)
        inventory_repo.get_slot = AsyncMock(return_value=(10, 10))  # item_id=10, amount=10
        inventory_repo.remove_item = AsyncMock(return_value=True)

        player_repo = MagicMock(spec=PlayerRepository)

        # Packet: BANK_DEPOSIT + slot=3 + quantity=5
        data = bytes([43, 3, 5, 0])  # quantity en little-endian

        session_data = {"user_id": 1}

        task = TaskBankDeposit(
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
        inventory_repo.get_slot.assert_called_once_with(1, 3)
        bank_repo.deposit_item.assert_called_once_with(1, 10, 5)
        inventory_repo.remove_item.assert_called_once_with(1, 3, 5)
        message_sender.send_change_inventory_slot.assert_called_once()
        message_sender.send_change_bank_slot.assert_called_once()
        message_sender.send_console_msg.assert_called()

    async def test_deposit_without_session(self) -> None:
        """Test de depósito sin sesión activa."""
        # Setup
        message_sender = MagicMock()
        bank_repo = MagicMock(spec=BankRepository)
        inventory_repo = MagicMock(spec=InventoryRepository)
        player_repo = MagicMock(spec=PlayerRepository)

        data = bytes([43, 1, 1, 0])
        session_data = {}  # Sin user_id

        task = TaskBankDeposit(
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
        bank_repo.deposit_item.assert_not_called()

    async def test_deposit_invalid_quantity(self) -> None:
        """Test de depósito con cantidad inválida."""
        # Setup
        message_sender = MagicMock()
        message_sender.send_console_msg = AsyncMock()

        bank_repo = MagicMock(spec=BankRepository)
        inventory_repo = MagicMock(spec=InventoryRepository)
        player_repo = MagicMock(spec=PlayerRepository)

        # Packet con cantidad 0
        data = bytes([43, 1, 0, 0])

        session_data = {"user_id": 1}

        task = TaskBankDeposit(
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
        bank_repo.deposit_item.assert_not_called()

    async def test_deposit_empty_slot(self) -> None:
        """Test de depósito desde slot vacío."""
        # Setup
        message_sender = MagicMock()
        message_sender.send_console_msg = AsyncMock()

        bank_repo = MagicMock(spec=BankRepository)
        inventory_repo = MagicMock(spec=InventoryRepository)
        inventory_repo.get_slot = AsyncMock(return_value=None)  # Slot vacío

        player_repo = MagicMock(spec=PlayerRepository)

        data = bytes([43, 1, 5, 0])
        session_data = {"user_id": 1}

        task = TaskBankDeposit(
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
        message_sender.send_console_msg.assert_called_with("No tienes ningún item en ese slot")
        bank_repo.deposit_item.assert_not_called()

    async def test_deposit_insufficient_quantity(self) -> None:
        """Test de depósito con cantidad insuficiente."""
        # Setup
        message_sender = MagicMock()
        message_sender.send_console_msg = AsyncMock()

        bank_repo = MagicMock(spec=BankRepository)
        inventory_repo = MagicMock(spec=InventoryRepository)
        inventory_repo.get_slot = AsyncMock(return_value=(10, 3))  # Solo 3 items

        player_repo = MagicMock(spec=PlayerRepository)

        # Intentar depositar 5 items
        data = bytes([43, 1, 5, 0])
        session_data = {"user_id": 1}

        task = TaskBankDeposit(
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
        message_sender.send_console_msg.assert_called_with("Solo tienes 3 items en ese slot")
        bank_repo.deposit_item.assert_not_called()

    async def test_deposit_bank_full(self) -> None:
        """Test de depósito cuando el banco está lleno."""
        # Setup
        message_sender = MagicMock()
        message_sender.send_console_msg = AsyncMock()

        bank_repo = MagicMock(spec=BankRepository)
        bank_repo.deposit_item = AsyncMock(return_value=None)  # No hay espacio

        inventory_repo = MagicMock(spec=InventoryRepository)
        inventory_repo.get_slot = AsyncMock(return_value=(10, 5))

        player_repo = MagicMock(spec=PlayerRepository)

        data = bytes([43, 1, 5, 0])
        session_data = {"user_id": 1}

        task = TaskBankDeposit(
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
        message_sender.send_console_msg.assert_called_with("No tienes espacio en el banco")
        inventory_repo.remove_item.assert_not_called()

    async def test_deposit_remove_fails(self) -> None:
        """Test cuando falla la remoción del inventario."""
        # Setup
        message_sender = MagicMock()
        message_sender.send_console_msg = AsyncMock()

        bank_repo = MagicMock(spec=BankRepository)
        bank_repo.deposit_item = AsyncMock(return_value=1)

        inventory_repo = MagicMock(spec=InventoryRepository)
        inventory_repo.get_slot = AsyncMock(return_value=(10, 5))
        inventory_repo.remove_item = AsyncMock(return_value=False)  # Falla

        player_repo = MagicMock(spec=PlayerRepository)

        data = bytes([43, 1, 5, 0])
        session_data = {"user_id": 1}

        task = TaskBankDeposit(
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
        message_sender.send_console_msg.assert_called_with("Error al depositar")
        message_sender.send_change_inventory_slot.assert_not_called()

    async def test_deposit_invalid_packet_size(self) -> None:
        """Test con packet de tamaño inválido."""
        # Setup
        message_sender = MagicMock()
        bank_repo = MagicMock(spec=BankRepository)
        inventory_repo = MagicMock(spec=InventoryRepository)
        player_repo = MagicMock(spec=PlayerRepository)

        # Packet muy corto
        data = bytes([43, 1])  # Falta quantity

        session_data = {"user_id": 1}

        task = TaskBankDeposit(
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
        bank_repo.deposit_item.assert_not_called()

    async def test_deposit_without_dependencies(self) -> None:
        """Test sin dependencias disponibles."""
        # Setup
        message_sender = MagicMock()
        message_sender.send_console_msg = AsyncMock()

        data = bytes([43, 1, 5, 0])
        session_data = {"user_id": 1}

        task = TaskBankDeposit(
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
        message_sender.send_console_msg.assert_called_with("Error al depositar en el banco")
