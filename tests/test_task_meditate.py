"""Tests para TaskMeditate."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.player_repository import PlayerRepository
from src.task_meditate import TaskMeditate


@pytest.mark.asyncio
class TestTaskMeditate:
    """Tests para TaskMeditate."""

    async def test_meditate_recovers_mana(self) -> None:
        """Test de meditación recupera mana."""
        # Setup
        message_sender = MagicMock()
        message_sender.send_console_msg = AsyncMock()
        message_sender.send_update_user_stats = AsyncMock()
        message_sender.send_meditate_toggle = AsyncMock()

        player_repo = MagicMock(spec=PlayerRepository)
        player_repo.get_stats = AsyncMock(
            return_value={
                "min_hp": 100,
                "max_hp": 100,
                "min_mana": 50,
                "max_mana": 100,
                "min_sta": 100,
                "max_sta": 100,
                "gold": 0,
                "level": 1,
                "elu": 300,
                "exp": 0,
            }
        )
        player_repo.set_stats = AsyncMock()

        # Packet: MEDITATE (79)
        data = bytes([79])
        session_data = {"user_id": 1}

        task = TaskMeditate(data, message_sender, player_repo, session_data)

        # Execute
        await task.execute()

        # Assert
        player_repo.set_stats.assert_called_once()
        call_kwargs = player_repo.set_stats.call_args[1]
        assert call_kwargs["min_mana"] == 60  # 50 + 10

        message_sender.send_update_user_stats.assert_called_once()
        message_sender.send_meditate_toggle.assert_called_once()
        message_sender.send_console_msg.assert_called_once()

    async def test_meditate_full_mana(self) -> None:
        """Test de meditación con mana completo."""
        # Setup
        message_sender = MagicMock()
        message_sender.send_console_msg = AsyncMock()

        player_repo = MagicMock(spec=PlayerRepository)
        player_repo.get_stats = AsyncMock(
            return_value={
                "min_hp": 100,
                "max_hp": 100,
                "min_mana": 100,  # Mana completo
                "max_mana": 100,
                "min_sta": 100,
                "max_sta": 100,
                "gold": 0,
                "level": 1,
                "elu": 300,
                "exp": 0,
            }
        )

        data = bytes([79])
        session_data = {"user_id": 1}

        task = TaskMeditate(data, message_sender, player_repo, session_data)

        # Execute
        await task.execute()

        # Assert - no debe actualizar stats
        message_sender.send_console_msg.assert_called_once()
        call_args = message_sender.send_console_msg.call_args[0][0]
        assert "completo" in call_args

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
        player_repo.get_stats.assert_not_called()

    async def test_meditate_caps_at_max_mana(self) -> None:
        """Test de meditación no excede mana máximo."""
        # Setup
        message_sender = MagicMock()
        message_sender.send_console_msg = AsyncMock()
        message_sender.send_update_user_stats = AsyncMock()
        message_sender.send_meditate_toggle = AsyncMock()

        player_repo = MagicMock(spec=PlayerRepository)
        player_repo.get_stats = AsyncMock(
            return_value={
                "min_hp": 100,
                "max_hp": 100,
                "min_mana": 95,  # Cerca del máximo
                "max_mana": 100,
                "min_sta": 100,
                "max_sta": 100,
                "gold": 0,
                "level": 1,
                "elu": 300,
                "exp": 0,
            }
        )
        player_repo.set_stats = AsyncMock()

        data = bytes([79])
        session_data = {"user_id": 1}

        task = TaskMeditate(data, message_sender, player_repo, session_data)

        # Execute
        await task.execute()

        # Assert - debe limitarse a 100
        call_kwargs = player_repo.set_stats.call_args[1]
        assert call_kwargs["min_mana"] == 100  # No debe exceder max_mana
