"""Tests para TaskBankEnd."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.task_bank_end import TaskBankEnd


@pytest.mark.asyncio
class TestTaskBankEnd:
    """Tests para TaskBankEnd."""

    async def test_bank_end_with_session(self) -> None:
        """Test de cerrar banco con sesión activa."""
        # Setup
        message_sender = MagicMock()
        message_sender.send_bank_end = AsyncMock()

        # Packet: BANK_END (solo PacketID)
        data = bytes([0x15])

        session_data = {"user_id": 1}

        task = TaskBankEnd(data, message_sender, session_data)

        # Execute
        await task.execute()

        # Assert - no debe crashear, solo loguear
        # No hay assertions específicas ya que solo loguea

    async def test_bank_end_without_session(self) -> None:
        """Test de cerrar banco sin sesión (pre-login)."""
        # Setup
        message_sender = MagicMock()

        data = bytes([0x15])
        session_data = {}  # Sin user_id

        task = TaskBankEnd(data, message_sender, session_data)

        # Execute
        await task.execute()

        # Assert - no debe crashear
        # Es normal recibir este paquete antes del login

    async def test_bank_end_minimal(self) -> None:
        """Test básico de TaskBankEnd."""
        # Setup
        message_sender = MagicMock()
        message_sender.send_bank_end = AsyncMock()
        data = bytes([0x15])
        session_data = {"user_id": 42}

        task = TaskBankEnd(data, message_sender, session_data)

        # Execute - debe completar sin errores
        await task.execute()

        # Verify
        message_sender.send_bank_end.assert_called_once()

        # Assert - simplemente verificar que no crashea
        assert task.session_data["user_id"] == 42
