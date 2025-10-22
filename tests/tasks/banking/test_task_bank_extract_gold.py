"""Tests para TaskBankExtractGold."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.repositories.bank_repository import BankRepository
from src.repositories.player_repository import PlayerRepository
from src.tasks.banking.task_bank_extract_gold import TaskBankExtractGold


@pytest.mark.asyncio
class TestTaskBankExtractGold:
    """Tests para TaskBankExtractGold."""

    async def test_extract_gold_success(self) -> None:
        """Test de retiro de oro exitoso."""
        # Setup
        message_sender = MagicMock()
        message_sender.connection.address = "127.0.0.1:1234"
        message_sender.send_console_msg = AsyncMock()
        message_sender.send_update_gold = AsyncMock()
        message_sender.send_update_bank_gold = AsyncMock()

        bank_repo = MagicMock(spec=BankRepository)
        bank_repo.get_gold = AsyncMock(side_effect=[1000, 900])  # Antes: 1000, Después: 900
        bank_repo.remove_gold = AsyncMock(return_value=True)

        player_repo = MagicMock(spec=PlayerRepository)
        player_repo.add_gold = AsyncMock(return_value=500)
        player_repo.get_gold = AsyncMock(return_value=500)  # Oro del jugador después

        # Packet: BANK_EXTRACT_GOLD + amount=100
        data = bytes([0x6F, 0x64, 0x00, 0x00, 0x00])  # 111 + 100 en int32

        session_data = {"user_id": 1}

        task = TaskBankExtractGold(
            data,
            message_sender,
            amount=100,
            bank_repo=bank_repo,
            player_repo=player_repo,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert
        assert bank_repo.get_gold.call_count == 2  # Se llama 2 veces (verificar + actualizar)
        bank_repo.remove_gold.assert_called_once_with(1, 100)
        player_repo.add_gold.assert_called_once_with(1, 100)
        player_repo.get_gold.assert_called_once_with(1)
        message_sender.send_update_gold.assert_called_once_with(500)
        message_sender.send_update_bank_gold.assert_called_once_with(900)  # Oro en banco después
        message_sender.send_console_msg.assert_called_once()

    async def test_extract_gold_amount_zero(self) -> None:
        """Test de retiro con cantidad 0."""
        # Setup
        message_sender = MagicMock()
        message_sender.connection.address = "127.0.0.1:1234"
        message_sender.send_console_msg = AsyncMock()

        bank_repo = MagicMock(spec=BankRepository)
        player_repo = MagicMock(spec=PlayerRepository)

        data = bytes([0x6F, 0x00, 0x00, 0x00, 0x00])
        session_data = {"user_id": 1}

        task = TaskBankExtractGold(
            data,
            message_sender,
            amount=0,
            bank_repo=bank_repo,
            player_repo=player_repo,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert - debe enviar mensaje de error
        message_sender.send_console_msg.assert_called_once()
        assert "mayor a 0" in message_sender.send_console_msg.call_args[0][0]
        bank_repo.remove_gold.assert_not_called()
        player_repo.add_gold.assert_not_called()

    async def test_extract_gold_insufficient_funds(self) -> None:
        """Test de retiro sin suficiente oro en banco."""
        # Setup
        message_sender = MagicMock()
        message_sender.connection.address = "127.0.0.1:1234"
        message_sender.send_console_msg = AsyncMock()

        bank_repo = MagicMock(spec=BankRepository)
        bank_repo.get_gold = AsyncMock(return_value=50)  # Solo tiene 50

        player_repo = MagicMock(spec=PlayerRepository)

        data = bytes([0x6F, 0x64, 0x00, 0x00, 0x00])
        session_data = {"user_id": 1}

        task = TaskBankExtractGold(
            data,
            message_sender,
            amount=100,  # Intenta retirar 100
            bank_repo=bank_repo,
            player_repo=player_repo,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert
        message_sender.send_console_msg.assert_called_once()
        assert "No tienes suficiente oro" in message_sender.send_console_msg.call_args[0][0]
        bank_repo.remove_gold.assert_not_called()
        player_repo.add_gold.assert_not_called()

    async def test_extract_gold_without_session(self) -> None:
        """Test sin sesión activa."""
        # Setup
        message_sender = MagicMock()
        bank_repo = MagicMock(spec=BankRepository)
        player_repo = MagicMock(spec=PlayerRepository)

        data = bytes([0x6F, 0x64, 0x00, 0x00, 0x00])
        session_data = {}  # Sin user_id

        task = TaskBankExtractGold(
            data,
            message_sender,
            amount=100,
            bank_repo=bank_repo,
            player_repo=player_repo,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert - no debe llamar a ningún método
        bank_repo.get_gold.assert_not_called()
        bank_repo.remove_gold.assert_not_called()
        player_repo.add_gold.assert_not_called()

    async def test_extract_gold_without_dependencies(self) -> None:
        """Test sin dependencias necesarias."""
        # Setup
        message_sender = MagicMock()
        message_sender.connection.address = "127.0.0.1:1234"
        message_sender.send_console_msg = AsyncMock()

        data = bytes([0x6F, 0x64, 0x00, 0x00, 0x00])
        session_data = {"user_id": 1}

        task = TaskBankExtractGold(
            data,
            message_sender,
            amount=100,
            bank_repo=None,  # Sin dependencias
            player_repo=None,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert
        message_sender.send_console_msg.assert_called_once()
        assert "Error" in message_sender.send_console_msg.call_args[0][0]
