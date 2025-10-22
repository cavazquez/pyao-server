"""Tests para TaskMeditate."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.player_repository import PlayerRepository
from src.tasks.player.task_meditate import TaskMeditate


@pytest.mark.asyncio
class TestTaskMeditate:
    """Tests para TaskMeditate con mecánica de toggle."""

    async def test_meditate_toggle_on(self) -> None:
        """Test de activar meditación."""
        # Setup
        message_sender = MagicMock()
        message_sender.send_console_msg = AsyncMock()
        message_sender.send_meditate_toggle = AsyncMock()

        player_repo = MagicMock(spec=PlayerRepository)
        player_repo.is_meditating = AsyncMock(return_value=False)  # No está meditando
        player_repo.set_meditating = AsyncMock()

        # Packet: MEDITATE (79)
        data = bytes([79])
        session_data = {"user_id": 1}

        task = TaskMeditate(data, message_sender, player_repo, session_data)

        # Execute
        await task.execute()

        # Assert - debe activar meditación
        player_repo.set_meditating.assert_called_once()
        message_sender.send_meditate_toggle.assert_called_once()
        message_sender.send_console_msg.assert_called_once()

    async def test_meditate_toggle_off(self) -> None:
        """Test de desactivar meditación."""
        # Setup
        message_sender = MagicMock()
        message_sender.send_console_msg = AsyncMock()
        message_sender.send_meditate_toggle = AsyncMock()

        player_repo = MagicMock(spec=PlayerRepository)
        player_repo.is_meditating = AsyncMock(return_value=True)  # Está meditando
        player_repo.set_meditating = AsyncMock()

        data = bytes([79])
        session_data = {"user_id": 1}

        task = TaskMeditate(data, message_sender, player_repo, session_data)

        # Execute
        await task.execute()

        # Assert - debe desactivar meditación
        player_repo.set_meditating.assert_called_once()
        message_sender.send_meditate_toggle.assert_called_once()
        message_sender.send_console_msg.assert_called_once()

    async def test_meditate_without_session(self) -> None:
        """Test de meditación sin sesión."""
        # Setup
        message_sender = MagicMock()
        player_repo = MagicMock(spec=PlayerRepository)

        data = bytes([79])
        session_data = {}  # Sin user_id

        task = TaskMeditate(data, message_sender, player_repo, session_data)

        # Execute
        await task.execute()

        # Assert - no debe hacer nada
        player_repo.is_meditating.assert_not_called()
