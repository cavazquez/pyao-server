"""Tests para TaskSpellInfo."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.tasks.spells.task_spell_info import TaskSpellInfo


@pytest.mark.asyncio
class TestTaskSpellInfo:
    """Suite de tests para TaskSpellInfo."""

    async def test_spell_info_success(self) -> None:
        """Envía información del hechizo cuando existe en el libro."""
        message_sender = MagicMock()
        message_sender.send_multiline_console_msg = AsyncMock()
        message_sender.send_console_msg = AsyncMock()

        spellbook_repo = MagicMock()
        spellbook_repo.get_spell_in_slot = AsyncMock(return_value=1)

        spell_catalog = MagicMock()
        spell_catalog.get_spell_data.return_value = {
            "name": "Dardo Mágico",
            "description": "Lanza un proyectil mágico.",
            "min_skill": 10,
            "mana_cost": 12,
            "stamina_cost": 1,
        }

        task = TaskSpellInfo(
            data=bytes([35, 1]),
            message_sender=message_sender,
            spellbook_repo=spellbook_repo,
            spell_catalog=spell_catalog,
            session_data={"user_id": 42},
            slot=1,
        )

        await task.execute()

        expected_message = (
            "%%%%%%%%%%%% INFO DEL HECHIZO %%%%%%%%%%%%\n"
            "Nombre: Dardo Mágico\n"
            "Descripción: Lanza un proyectil mágico.\n"
            "Skill requerido: 10 de magia.\n"
            "Maná necesario: 12\n"
            "Energía necesaria: 1\n"
            "%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%"
        )

        message_sender.send_multiline_console_msg.assert_awaited_once_with(expected_message)
        message_sender.send_console_msg.assert_not_awaited()

    async def test_spell_info_slot_empty(self) -> None:
        """Envía mensaje de error cuando el slot no tiene hechizo."""
        message_sender = MagicMock()
        message_sender.send_multiline_console_msg = AsyncMock()
        message_sender.send_console_msg = AsyncMock()

        spellbook_repo = MagicMock()
        spellbook_repo.get_spell_in_slot = AsyncMock(return_value=None)

        spell_catalog = MagicMock()

        task = TaskSpellInfo(
            data=bytes([35, 2]),
            message_sender=message_sender,
            spellbook_repo=spellbook_repo,
            spell_catalog=spell_catalog,
            session_data={"user_id": 7},
            slot=2,
        )

        await task.execute()

        message_sender.send_console_msg.assert_awaited_once_with("¡Primero selecciona el hechizo!")
        message_sender.send_multiline_console_msg.assert_not_awaited()

    async def test_spell_info_missing_catalog_data(self) -> None:
        """Notifica cuando el hechizo no existe en el catálogo."""
        message_sender = MagicMock()
        message_sender.send_multiline_console_msg = AsyncMock()
        message_sender.send_console_msg = AsyncMock()

        spellbook_repo = MagicMock()
        spellbook_repo.get_spell_in_slot = AsyncMock(return_value=5)

        spell_catalog = MagicMock()
        spell_catalog.get_spell_data.return_value = None

        task = TaskSpellInfo(
            data=bytes([35, 5]),
            message_sender=message_sender,
            spellbook_repo=spellbook_repo,
            spell_catalog=spell_catalog,
            session_data={"user_id": 99},
            slot=5,
        )

        await task.execute()

        message_sender.send_console_msg.assert_awaited_once_with(
            "Datos del hechizo no disponibles."
        )
        message_sender.send_multiline_console_msg.assert_not_awaited()

    async def test_spell_info_without_session(self) -> None:
        """No hace nada si no hay sesión activa."""
        message_sender = MagicMock()
        message_sender.send_multiline_console_msg = AsyncMock()
        message_sender.send_console_msg = AsyncMock()

        spellbook_repo = MagicMock()
        spellbook_repo.get_spell_in_slot = AsyncMock()

        spell_catalog = MagicMock()

        task = TaskSpellInfo(
            data=bytes([35, 1]),
            message_sender=message_sender,
            spellbook_repo=spellbook_repo,
            spell_catalog=spell_catalog,
            session_data={},
        )

        await task.execute()

        spellbook_repo.get_spell_in_slot.assert_not_awaited()
        message_sender.send_console_msg.assert_not_awaited()
        message_sender.send_multiline_console_msg.assert_not_awaited()
