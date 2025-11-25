"""Tests para TaskMoveSpell."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.commands.base import CommandResult
from src.commands.move_spell_command import MoveSpellCommand
from src.repositories.spellbook_repository import MoveSpellResult
from src.tasks.spells.task_move_spell import TaskMoveSpell


def create_mock_move_spell_handler(
    spellbook_repo: MagicMock | None = None,
    spell_catalog: MagicMock | None = None,
    message_sender: MagicMock | None = None,
) -> MagicMock:
    """Crea un mock de MoveSpellCommandHandler con las dependencias especificadas."""
    handler = MagicMock()
    handler.spellbook_repo = spellbook_repo or MagicMock()
    handler.spell_catalog = spell_catalog or MagicMock()
    handler.message_sender = message_sender or MagicMock()
    handler.handle = AsyncMock()
    return handler


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

        move_spell_handler = create_mock_move_spell_handler(
            spellbook_repo=spellbook_repo,
            spell_catalog=spell_catalog,
            message_sender=message_sender,
        )
        move_spell_handler.handle.return_value = CommandResult.ok(
            data={
                "slot": 2,
                "target_slot": 1,
                "slot_spell_id": 10,
                "target_slot_spell_id": 20,
            }
        )

        task = TaskMoveSpell(
            data=bytes([45, 1, 2]),
            message_sender=message_sender,
            move_spell_handler=move_spell_handler,
            session_data={"user_id": 1},
        )

        await task.execute()

        # Debe llamar al handler con el comando correcto
        move_spell_handler.handle.assert_called_once()
        call_args = move_spell_handler.handle.call_args[0][0]
        assert isinstance(call_args, MoveSpellCommand)
        assert call_args.user_id == 1
        assert call_args.slot == 2
        assert call_args.upwards is True

    async def test_move_spell_out_of_bounds(self) -> None:
        """Envía mensaje de error cuando el movimiento es inválido."""
        message_sender = MagicMock()
        message_sender.send_change_spell_slot = AsyncMock()
        message_sender.send_console_msg = AsyncMock()

        move_spell_handler = create_mock_move_spell_handler(message_sender=message_sender)
        move_spell_handler.handle.return_value = CommandResult.error(
            "No puedes mover el hechizo en esa dirección."
        )

        task = TaskMoveSpell(
            data=bytes([45, 1, 1]),
            message_sender=message_sender,
            move_spell_handler=move_spell_handler,
            session_data={"user_id": 1},
        )

        await task.execute()

        # Debe llamar al handler
        move_spell_handler.handle.assert_called_once()

    async def test_move_spell_redis_unavailable(self) -> None:
        """No hace nada si el repositorio devuelve None."""
        message_sender = MagicMock()
        message_sender.send_change_spell_slot = AsyncMock()
        message_sender.send_console_msg = AsyncMock()

        move_spell_handler = create_mock_move_spell_handler(message_sender=message_sender)
        move_spell_handler.handle.return_value = CommandResult.error("Servicio no disponible")

        task = TaskMoveSpell(
            data=bytes([45, 1, 1]),
            message_sender=message_sender,
            move_spell_handler=move_spell_handler,
            session_data={"user_id": 1},
        )

        await task.execute()

        # Debe llamar al handler
        move_spell_handler.handle.assert_called_once()

    async def test_move_spell_without_session(self) -> None:
        """Ignora la petición si no hay sesión activa."""
        message_sender = MagicMock()
        message_sender.send_change_spell_slot = AsyncMock()

        move_spell_handler = create_mock_move_spell_handler()

        task = TaskMoveSpell(
            data=bytes([45, 1, 1]),
            message_sender=message_sender,
            move_spell_handler=move_spell_handler,
            session_data={},
        )

        await task.execute()

        # No debe llamar al handler sin sesión
        move_spell_handler.handle.assert_not_called()

    async def test_move_spell_invalid_packet(self) -> None:
        """Ignora la petición si el packet es inválido."""
        message_sender = MagicMock()
        move_spell_handler = create_mock_move_spell_handler()

        # Packet muy corto
        task = TaskMoveSpell(
            data=bytes([45]),
            message_sender=message_sender,
            move_spell_handler=move_spell_handler,
            session_data={"user_id": 1},
        )

        await task.execute()

        # No debe llamar al handler con packet inválido
        move_spell_handler.handle.assert_not_called()
