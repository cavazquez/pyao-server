"""Tests para TaskSpellInfo."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.commands.base import CommandResult
from src.commands.spell_info_command import SpellInfoCommand
from src.tasks.spells.task_spell_info import TaskSpellInfo


@pytest.mark.asyncio
class TestTaskSpellInfo:
    """Suite de tests para TaskSpellInfo."""

    async def test_spell_info_success(self) -> None:
        """Envía información del hechizo cuando existe en el libro."""
        message_sender = MagicMock()
        message_sender.send_multiline_console_msg = AsyncMock()
        message_sender.send_console_msg = AsyncMock()

        # Mock del handler
        spell_info_handler = MagicMock()
        spell_info_handler.handle = AsyncMock(
            return_value=CommandResult.ok(
                data={
                    "user_id": 42,
                    "slot": 1,
                    "spell_id": 1,
                    "spell_data": {
                        "name": "Dardo Mágico",
                        "description": "Lanza un proyectil mágico.",
                        "min_skill": 10,
                        "mana_cost": 12,
                        "stamina_cost": 1,
                    },
                }
            )
        )

        task = TaskSpellInfo(
            data=bytes([35, 1]),
            message_sender=message_sender,
            spell_info_handler=spell_info_handler,
            session_data={"user_id": 42},
            slot=1,
        )

        await task.execute()

        # Verificar que se llamó al handler
        spell_info_handler.handle.assert_called_once()
        call_args = spell_info_handler.handle.call_args[0][0]
        assert isinstance(call_args, SpellInfoCommand)
        assert call_args.user_id == 42
        assert call_args.slot == 1

    async def test_spell_info_slot_empty(self) -> None:
        """Envía mensaje de error cuando el slot no tiene hechizo."""
        message_sender = MagicMock()
        message_sender.send_multiline_console_msg = AsyncMock()
        message_sender.send_console_msg = AsyncMock()

        # Mock del handler que retorna error
        spell_info_handler = MagicMock()
        spell_info_handler.handle = AsyncMock(return_value=CommandResult.error("Slot vacío"))

        task = TaskSpellInfo(
            data=bytes([35, 2]),
            message_sender=message_sender,
            spell_info_handler=spell_info_handler,
            session_data={"user_id": 7},
            slot=2,
        )

        await task.execute()

        # Verificar que se llamó al handler
        spell_info_handler.handle.assert_called_once()

    async def test_spell_info_missing_catalog_data(self) -> None:
        """Notifica cuando el hechizo no existe en el catálogo."""
        message_sender = MagicMock()
        message_sender.send_multiline_console_msg = AsyncMock()
        message_sender.send_console_msg = AsyncMock()

        # Mock del handler que retorna error
        spell_info_handler = MagicMock()
        spell_info_handler.handle = AsyncMock(
            return_value=CommandResult.error("Datos del hechizo no disponibles")
        )

        task = TaskSpellInfo(
            data=bytes([35, 5]),
            message_sender=message_sender,
            spell_info_handler=spell_info_handler,
            session_data={"user_id": 99},
            slot=5,
        )

        await task.execute()

        # Verificar que se llamó al handler
        spell_info_handler.handle.assert_called_once()

    async def test_spell_info_without_session(self) -> None:
        """No hace nada si no hay sesión activa."""
        message_sender = MagicMock()
        message_sender.send_multiline_console_msg = AsyncMock()
        message_sender.send_console_msg = AsyncMock()

        # Mock del handler (no debería llamarse)
        spell_info_handler = MagicMock()
        spell_info_handler.handle = AsyncMock()

        task = TaskSpellInfo(
            data=bytes([35, 1]),
            message_sender=message_sender,
            spell_info_handler=spell_info_handler,
            session_data={},
        )

        await task.execute()

        # Verificar que NO se llamó al handler
        spell_info_handler.handle.assert_not_called()
