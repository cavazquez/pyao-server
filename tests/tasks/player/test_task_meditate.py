"""Tests para TaskMeditate."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.commands.base import CommandResult
from src.commands.meditate_command import MeditateCommand
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
        message_sender.send_create_fx = AsyncMock()

        # Mock del handler
        meditate_handler = MagicMock()
        meditate_handler.handle = AsyncMock(
            return_value=CommandResult.ok(data={"user_id": 1, "is_meditating": True})
        )

        # Packet: MEDITATE (79)
        data = bytes([79])
        session_data = {"user_id": 1}

        task = TaskMeditate(
            data, message_sender, meditate_handler=meditate_handler, session_data=session_data
        )

        # Execute
        await task.execute()

        # Assert - debe llamar al handler
        meditate_handler.handle.assert_called_once()
        call_args = meditate_handler.handle.call_args[0][0]
        assert isinstance(call_args, MeditateCommand)
        assert call_args.user_id == 1

    async def test_meditate_toggle_off(self) -> None:
        """Test de desactivar meditación."""
        # Setup
        message_sender = MagicMock()
        message_sender.send_console_msg = AsyncMock()
        message_sender.send_meditate_toggle = AsyncMock()
        message_sender.send_create_fx = AsyncMock()

        # Mock del handler
        meditate_handler = MagicMock()
        meditate_handler.handle = AsyncMock(
            return_value=CommandResult.ok(data={"user_id": 1, "is_meditating": False})
        )

        data = bytes([79])
        session_data = {"user_id": 1}

        task = TaskMeditate(
            data, message_sender, meditate_handler=meditate_handler, session_data=session_data
        )

        # Execute
        await task.execute()

        # Assert - debe llamar al handler
        meditate_handler.handle.assert_called_once()
        call_args = meditate_handler.handle.call_args[0][0]
        assert isinstance(call_args, MeditateCommand)
        assert call_args.user_id == 1

    async def test_meditate_without_session(self) -> None:
        """Test de meditación sin sesión."""
        # Setup
        message_sender = MagicMock()

        # Mock del handler (no debería llamarse si no hay user_id)
        meditate_handler = MagicMock()
        meditate_handler.handle = AsyncMock()

        data = bytes([79])
        session_data = {}  # Sin user_id

        task = TaskMeditate(
            data, message_sender, meditate_handler=meditate_handler, session_data=session_data
        )

        # Execute
        await task.execute()

        # Assert - no debe llamar al handler
        meditate_handler.handle.assert_not_called()

    async def test_meditate_handler_not_available(self) -> None:
        """Test de meditación cuando el handler no está disponible."""
        # Setup
        message_sender = MagicMock()

        data = bytes([79])
        session_data = {"user_id": 1}

        # Sin handler
        task = TaskMeditate(data, message_sender, meditate_handler=None, session_data=session_data)

        # Execute
        await task.execute()

        # El test pasa si no hay excepciones (solo se loguea error)
