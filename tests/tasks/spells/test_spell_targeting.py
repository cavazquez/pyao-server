"""Tests para sistema de targeting de hechizos."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.repositories.player_repository import PlayerRepository
from src.services.player.spell_service import SpellService
from src.tasks.spells.task_cast_spell import TaskCastSpell


class TestSpellTargeting:
    """Tests para targeting de hechizos."""

    @pytest.mark.asyncio
    async def test_cast_spell_with_valid_target(self) -> None:
        """Test lanzar hechizo con target válido."""
        message_sender = MagicMock()
        message_sender.send_console_msg = AsyncMock()

        player_repo = MagicMock(spec=PlayerRepository)
        player_repo.get_position = AsyncMock(
            return_value={"map": 1, "x": 50, "y": 50, "heading": 3}
        )

        spell_service = MagicMock(spec=SpellService)
        spell_service.cast_spell = AsyncMock(return_value=True)

        spellbook_repo = MagicMock()
        spellbook_repo.get_spell_in_slot = AsyncMock(return_value=1)

        # Target a 5 tiles de distancia (dentro del rango)
        data = bytes([25, 1, 55, 0, 50, 0])  # X=55, Y=50
        session_data = {"user_id": 1}

        task = TaskCastSpell(
            data, message_sender, player_repo, spell_service, None, session_data, spellbook_repo
        )

        await task.execute()

        # Debe lanzar el hechizo
        spell_service.cast_spell.assert_called_once()
        call_args = spell_service.cast_spell.call_args[0]
        assert call_args[2] == 55  # target_x
        assert call_args[3] == 50  # target_y

    @pytest.mark.asyncio
    async def test_cast_spell_out_of_range(self) -> None:
        """Test lanzar hechizo fuera de rango."""
        message_sender = MagicMock()
        message_sender.send_console_msg = AsyncMock()

        player_repo = MagicMock(spec=PlayerRepository)
        player_repo.get_position = AsyncMock(
            return_value={"map": 1, "x": 50, "y": 50, "heading": 3}
        )

        spell_service = MagicMock(spec=SpellService)
        spell_service.cast_spell = AsyncMock(return_value=True)

        spellbook_repo = MagicMock()
        spellbook_repo.get_spell_in_slot = AsyncMock(return_value=1)

        # Target a 15 tiles de distancia (fuera del rango máximo de 10)
        data = bytes([25, 1, 65, 0, 50, 0])  # X=65, Y=50 (distancia=15)
        session_data = {"user_id": 1}

        task = TaskCastSpell(
            data, message_sender, player_repo, spell_service, None, session_data, spellbook_repo
        )

        await task.execute()

        # No debe lanzar el hechizo
        spell_service.cast_spell.assert_not_called()
        # Debe enviar mensaje de error
        message_sender.send_console_msg.assert_called_once()

    @pytest.mark.asyncio
    async def test_cast_spell_diagonal_target(self) -> None:
        """Test lanzar hechizo con target diagonal."""
        message_sender = MagicMock()
        message_sender.send_console_msg = AsyncMock()

        player_repo = MagicMock(spec=PlayerRepository)
        player_repo.get_position = AsyncMock(
            return_value={"map": 1, "x": 50, "y": 50, "heading": 3}
        )

        spell_service = MagicMock(spec=SpellService)
        spell_service.cast_spell = AsyncMock(return_value=True)

        spellbook_repo = MagicMock()
        spellbook_repo.get_spell_in_slot = AsyncMock(return_value=1)

        # Target diagonal a 3+3=6 tiles de distancia (Manhattan)
        data = bytes([25, 1, 53, 0, 53, 0])  # X=53, Y=53
        session_data = {"user_id": 1}

        task = TaskCastSpell(
            data, message_sender, player_repo, spell_service, None, session_data, spellbook_repo
        )

        await task.execute()

        # Debe lanzar el hechizo
        spell_service.cast_spell.assert_called_once()
        call_args = spell_service.cast_spell.call_args[0]
        assert call_args[2] == 53  # target_x
        assert call_args[3] == 53  # target_y

    @pytest.mark.asyncio
    async def test_cast_spell_same_position(self) -> None:
        """Test lanzar hechizo en la misma posición del jugador."""
        message_sender = MagicMock()
        message_sender.send_console_msg = AsyncMock()

        player_repo = MagicMock(spec=PlayerRepository)
        player_repo.get_position = AsyncMock(
            return_value={"map": 1, "x": 50, "y": 50, "heading": 3}
        )

        spell_service = MagicMock(spec=SpellService)
        spell_service.cast_spell = AsyncMock(return_value=True)

        spellbook_repo = MagicMock()
        spellbook_repo.get_spell_in_slot = AsyncMock(return_value=1)

        # Target en la misma posición (distancia=0)
        data = bytes([25, 1, 50, 0, 50, 0])  # X=50, Y=50
        session_data = {"user_id": 1}

        task = TaskCastSpell(
            data, message_sender, player_repo, spell_service, None, session_data, spellbook_repo
        )

        await task.execute()

        # Debe lanzar el hechizo (distancia 0 es válida)
        spell_service.cast_spell.assert_called_once()

    @pytest.mark.asyncio
    async def test_cast_spell_max_range(self) -> None:
        """Test lanzar hechizo en el límite del rango máximo."""
        message_sender = MagicMock()
        message_sender.send_console_msg = AsyncMock()

        player_repo = MagicMock(spec=PlayerRepository)
        player_repo.get_position = AsyncMock(
            return_value={"map": 1, "x": 50, "y": 50, "heading": 3}
        )

        spell_service = MagicMock(spec=SpellService)
        spell_service.cast_spell = AsyncMock(return_value=True)

        spellbook_repo = MagicMock()
        spellbook_repo.get_spell_in_slot = AsyncMock(return_value=1)

        # Target exactamente a 10 tiles de distancia (límite)
        data = bytes([25, 1, 60, 0, 50, 0])  # X=60, Y=50 (distancia=10)
        session_data = {"user_id": 1}

        task = TaskCastSpell(
            data, message_sender, player_repo, spell_service, None, session_data, spellbook_repo
        )

        await task.execute()

        # Debe lanzar el hechizo (distancia 10 es válida)
        spell_service.cast_spell.assert_called_once()

    @pytest.mark.asyncio
    async def test_cast_spell_invalid_packet_size(self) -> None:
        """Test packet CAST_SPELL con tamaño inválido."""
        message_sender = MagicMock()
        message_sender.send_console_msg = AsyncMock()

        player_repo = MagicMock(spec=PlayerRepository)
        spell_service = MagicMock(spec=SpellService)
        spell_service.cast_spell = AsyncMock(return_value=True)

        spellbook_repo = MagicMock()

        # Packet incompleto (solo 1 byte en lugar de al menos 2)
        data = bytes([25])
        session_data = {"user_id": 1}

        task = TaskCastSpell(
            data, message_sender, player_repo, spell_service, None, session_data, spellbook_repo
        )

        await task.execute()

        # No debe lanzar el hechizo
        spell_service.cast_spell.assert_not_called()

    @pytest.mark.asyncio
    async def test_cast_spell_old_format(self) -> None:
        """Test lanzar hechizo con formato antiguo (sin coordenadas)."""
        message_sender = MagicMock()
        message_sender.send_console_msg = AsyncMock()

        player_repo = MagicMock(spec=PlayerRepository)
        player_repo.get_position = AsyncMock(
            return_value={"map": 1, "x": 50, "y": 50, "heading": 2}  # Este
        )

        spell_service = MagicMock(spec=SpellService)
        spell_service.cast_spell = AsyncMock(return_value=True)

        spellbook_repo = MagicMock()
        spellbook_repo.get_spell_in_slot = AsyncMock(return_value=1)

        # Packet formato antiguo (solo 2 bytes)
        data = bytes([25, 1])
        session_data = {"user_id": 1}

        task = TaskCastSpell(
            data, message_sender, player_repo, spell_service, None, session_data, spellbook_repo
        )

        await task.execute()

        # Debe lanzar el hechizo con target calculado según heading
        spell_service.cast_spell.assert_called_once()
        call_args = spell_service.cast_spell.call_args[0]
        assert call_args[0] == 1  # user_id
        assert call_args[1] == 1  # spell_id
        assert call_args[2] == 51  # target_x (50 + 1, hacia el Este)
        assert call_args[3] == 50  # target_y (sin cambio)
