"""Tests para TaskCastSpell."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.commands.base import CommandResult
from src.commands.cast_spell_command import CastSpellCommand
from src.tasks.spells.task_cast_spell import TaskCastSpell


def create_mock_cast_spell_handler(
    player_repo: MagicMock | None = None,
    spell_service: MagicMock | None = None,
    spellbook_repo: MagicMock | None = None,
    stamina_service: MagicMock | None = None,
    message_sender: MagicMock | None = None,
) -> MagicMock:
    """Crea un mock de CastSpellCommandHandler con las dependencias especificadas."""
    handler = MagicMock()
    handler.player_repo = player_repo or MagicMock()
    handler.spell_service = spell_service or MagicMock()
    handler.spellbook_repo = spellbook_repo or MagicMock()
    handler.stamina_service = stamina_service
    handler.message_sender = message_sender or MagicMock()
    handler.handle = AsyncMock()
    return handler


@pytest.mark.asyncio
class TestTaskCastSpell:
    """Tests para TaskCastSpell."""

    async def test_cast_spell_without_session(self) -> None:
        """Test de lanzar hechizo sin sesión."""
        # Setup
        message_sender = AsyncMock()
        cast_spell_handler = create_mock_cast_spell_handler(message_sender=message_sender)

        # Packet: CAST_SPELL (39) + Slot (1)
        data = bytes([39, 1, 0])  # 3 bytes mínimo (sin coordenadas)
        session_data = {}  # Sin user_id

        task = TaskCastSpell(
            data, message_sender, cast_spell_handler=cast_spell_handler, session_data=session_data
        )

        # Execute
        await task.execute()

        # Assert - no debe llamar al handler si no hay sesión
        cast_spell_handler.handle.assert_not_called()

    async def test_cast_spell_invalid_packet(self) -> None:
        """Test con packet inválido."""
        # Setup
        message_sender = AsyncMock()
        cast_spell_handler = create_mock_cast_spell_handler(message_sender=message_sender)

        # Packet muy corto
        data = bytes([39])  # Falta el slot
        session_data = {"user_id": 1}

        task = TaskCastSpell(
            data, message_sender, cast_spell_handler=cast_spell_handler, session_data=session_data
        )

        # Execute
        await task.execute()

        # Assert - no debe crashear ni llamar al handler
        cast_spell_handler.handle.assert_not_called()

    async def test_cast_spell_basic(self) -> None:
        """Test básico de lanzar hechizo."""
        # Setup
        message_sender = AsyncMock()
        cast_spell_handler = create_mock_cast_spell_handler(message_sender=message_sender)
        cast_spell_handler.handle.return_value = CommandResult.ok(
            data={"spell_id": 1, "target_x": 51, "target_y": 50, "slot": 1}
        )

        # Packet: CAST_SPELL (39) + Slot 1 + Target X=51 + Target Y=50 + padding
        data = bytes([39, 1, 51, 0, 50, 0, 0])  # 7 bytes total
        session_data = {"user_id": 1}

        task = TaskCastSpell(
            data, message_sender, cast_spell_handler=cast_spell_handler, session_data=session_data
        )

        # Execute
        await task.execute()

        # Assert - debe llamar al handler con el comando correcto
        cast_spell_handler.handle.assert_called_once()
        call_args = cast_spell_handler.handle.call_args[0][0]
        assert isinstance(call_args, CastSpellCommand)
        assert call_args.user_id == 1
        assert call_args.slot == 1
        assert call_args.target_x == 51
        assert call_args.target_y == 50
