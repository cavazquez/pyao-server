"""Tests para TaskMoveSpell."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.repositories.spellbook_repository import MoveSpellResult
from src.tasks.spells.task_move_spell import TaskMoveSpell


@pytest.mark.asyncio
class TestTaskMoveSpell:
    """Tests para el handler MOVE_SPELL."""

    async def test_move_spell_success(self) -> None:
        """Intercambia slots y envía actualizaciones."""
        message_sender = MagicMock()
        message_sender.send_change_spell_slot = AsyncMock()
        message_sender.send_console_msg = AsyncMock()

        spellbook_repo = MagicMock()
        spellbook_repo.move_spell = AsyncMock(
            return_value=MoveSpellResult(
                success=True,
                slot=2,
                target_slot=1,
                slot_spell_id=10,
                target_slot_spell_id=20,
            )
        )

        spell_catalog = MagicMock()
        spell_catalog.get_spell_data.side_effect = lambda spell_id: {"name": f"Spell {spell_id}"}

        task = TaskMoveSpell(
            data=bytes([45, 1, 2]),
            message_sender=message_sender,
            slot=2,
            upwards=True,
            session_data={"user_id": 1},
            spellbook_repo=spellbook_repo,
            spell_catalog=spell_catalog,
        )

        await task.execute()

        spellbook_repo.move_spell.assert_awaited_once_with(user_id=1, slot=2, upwards=True)
        message_sender.send_console_msg.assert_not_called()

        expected_calls = {
            (2, 10, "Spell 10"),
            (1, 20, "Spell 20"),
        }
        recorded_calls = {
            (
                call.kwargs["slot"],
                call.kwargs["spell_id"],
                call.kwargs["spell_name"],
            )
            for call in message_sender.send_change_spell_slot.await_args_list
        }
        assert recorded_calls == expected_calls

    async def test_move_spell_out_of_bounds(self) -> None:
        """Envía mensaje de error cuando el movimiento es inválido."""
        message_sender = MagicMock()
        message_sender.send_change_spell_slot = AsyncMock()
        message_sender.send_console_msg = AsyncMock()

        spellbook_repo = MagicMock()
        spellbook_repo.move_spell = AsyncMock(
            return_value=MoveSpellResult(
                success=False,
                slot=1,
                target_slot=0,
                slot_spell_id=None,
                target_slot_spell_id=None,
                reason="out_of_bounds",
            )
        )

        task = TaskMoveSpell(
            data=bytes([45, 1, 1]),
            message_sender=message_sender,
            slot=1,
            upwards=True,
            session_data={"user_id": 1},
            spellbook_repo=spellbook_repo,
        )

        await task.execute()

        message_sender.send_console_msg.assert_awaited_once()
        message_sender.send_change_spell_slot.assert_not_called()

    async def test_move_spell_redis_unavailable(self) -> None:
        """No hace nada si el repositorio devuelve None."""
        message_sender = MagicMock()
        message_sender.send_change_spell_slot = AsyncMock()
        message_sender.send_console_msg = AsyncMock()

        spellbook_repo = MagicMock()
        spellbook_repo.move_spell = AsyncMock(return_value=None)

        task = TaskMoveSpell(
            data=bytes([45, 1, 1]),
            message_sender=message_sender,
            slot=1,
            upwards=True,
            session_data={"user_id": 1},
            spellbook_repo=spellbook_repo,
        )

        await task.execute()

        message_sender.send_console_msg.assert_not_called()
        message_sender.send_change_spell_slot.assert_not_called()

    async def test_move_spell_without_session(self) -> None:
        """Ignora la petición si no hay sesión activa."""
        message_sender = MagicMock()
        message_sender.send_change_spell_slot = AsyncMock()

        spellbook_repo = MagicMock()
        spellbook_repo.move_spell = AsyncMock()

        task = TaskMoveSpell(
            data=bytes([45, 1, 1]),
            message_sender=message_sender,
            slot=1,
            upwards=True,
            session_data={},
            spellbook_repo=spellbook_repo,
        )

        await task.execute()

        spellbook_repo.move_spell.assert_not_called()
        message_sender.send_change_spell_slot.assert_not_called()
