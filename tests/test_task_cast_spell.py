"""Tests para TaskCastSpell."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.player_repository import PlayerRepository
from src.spell_service import SpellService
from src.task_cast_spell import TaskCastSpell


@pytest.mark.asyncio
class TestTaskCastSpell:
    """Tests para TaskCastSpell."""

    async def test_cast_spell_without_session(self) -> None:
        """Test de lanzar hechizo sin sesión."""
        # Setup
        message_sender = MagicMock()
        player_repo = MagicMock(spec=PlayerRepository)
        spell_service = MagicMock(spec=SpellService)
        stamina_service = MagicMock()
        stamina_service.consume_stamina = AsyncMock(return_value=True)

        # Packet: CAST_SPELL (25) + Slot (1)
        data = bytes([25, 1])
        session_data = {}  # Sin user_id

        task = TaskCastSpell(
            data, message_sender, player_repo, spell_service, stamina_service, session_data
        )

        # Execute
        await task.execute()

        # Assert - no debe hacer nada
        spell_service.cast_spell.assert_not_called()

    async def test_cast_spell_invalid_packet(self) -> None:
        """Test con packet inválido."""
        # Setup
        message_sender = MagicMock()
        player_repo = MagicMock(spec=PlayerRepository)
        spell_service = MagicMock(spec=SpellService)
        stamina_service = MagicMock()
        stamina_service.consume_stamina = AsyncMock(return_value=True)

        # Packet muy corto
        data = bytes([25])  # Falta el slot
        session_data = {"user_id": 1}

        task = TaskCastSpell(
            data, message_sender, player_repo, spell_service, stamina_service, session_data
        )

        # Execute
        await task.execute()

        # Assert - no debe crashear
        spell_service.cast_spell.assert_not_called()

    async def test_cast_spell_basic(self) -> None:
        """Test básico de lanzar hechizo."""
        # Setup
        message_sender = MagicMock()

        player_repo = MagicMock(spec=PlayerRepository)
        player_repo.get_position = AsyncMock(
            return_value={"map": 1, "x": 50, "y": 50, "heading": 3}
        )

        spell_service = MagicMock(spec=SpellService)
        spell_service.cast_spell = AsyncMock(return_value=True)

        stamina_service = MagicMock()
        stamina_service.consume_stamina = AsyncMock(return_value=True)

        spellbook_repo = MagicMock()
        spellbook_repo.get_spell_in_slot = AsyncMock(return_value=1)  # Dardo Mágico

        # Packet: CAST_SPELL + Slot 1 + Target X=51 + Target Y=50 (little-endian)
        data = bytes([25, 1, 51, 0, 50, 0])  # X=51, Y=50 en little-endian uint16
        session_data = {"user_id": 1}

        task = TaskCastSpell(
            data,
            message_sender,
            player_repo,
            spell_service,
            stamina_service,
            session_data,
            spellbook_repo,
        )

        # Execute
        await task.execute()

        # Assert - debe intentar lanzar hechizo
        spell_service.cast_spell.assert_called_once()
        call_args = spell_service.cast_spell.call_args[0]
        assert call_args[0] == 1  # user_id
        assert call_args[1] == 1  # spell_id (Dardo Mágico)
        assert call_args[2] == 51  # target_x
        assert call_args[3] == 50  # target_y
