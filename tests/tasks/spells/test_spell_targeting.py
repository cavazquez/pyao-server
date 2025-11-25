"""Tests para sistema de targeting de hechizos."""

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


class TestSpellTargeting:
    """Tests para targeting de hechizos."""

    @pytest.mark.asyncio
    async def test_cast_spell_with_valid_target(self) -> None:
        """Test lanzar hechizo con target válido."""
        message_sender = AsyncMock()
        cast_spell_handler = create_mock_cast_spell_handler(message_sender=message_sender)
        cast_spell_handler.handle.return_value = CommandResult.ok(
            data={"spell_id": 1, "target_x": 55, "target_y": 50, "slot": 1}
        )

        # Target a 5 tiles de distancia (dentro del rango)
        data = bytes([39, 1, 55, 0, 50, 0, 0])  # X=55, Y=50 + padding
        session_data = {"user_id": 1}

        task = TaskCastSpell(
            data, message_sender, cast_spell_handler=cast_spell_handler, session_data=session_data
        )

        await task.execute()

        # Debe llamar al handler
        cast_spell_handler.handle.assert_called_once()
        call_args = cast_spell_handler.handle.call_args[0][0]
        assert isinstance(call_args, CastSpellCommand)
        assert call_args.target_x == 55
        assert call_args.target_y == 50

    @pytest.mark.asyncio
    async def test_cast_spell_out_of_range(self) -> None:
        """Test lanzar hechizo fuera de rango."""
        message_sender = AsyncMock()
        cast_spell_handler = create_mock_cast_spell_handler(message_sender=message_sender)
        cast_spell_handler.handle.return_value = CommandResult.error(
            "El objetivo está demasiado lejos para lanzar el hechizo."
        )

        # Target a 15 tiles de distancia (fuera del rango máximo de 10)
        data = bytes([39, 1, 65, 0, 50, 0, 0])  # X=65, Y=50 + padding (distancia=15)
        session_data = {"user_id": 1}

        task = TaskCastSpell(
            data, message_sender, cast_spell_handler=cast_spell_handler, session_data=session_data
        )

        await task.execute()

        # Debe llamar al handler (la validación de rango está en el handler)
        cast_spell_handler.handle.assert_called_once()

    @pytest.mark.asyncio
    async def test_cast_spell_diagonal_target(self) -> None:
        """Test lanzar hechizo con target diagonal."""
        message_sender = AsyncMock()
        cast_spell_handler = create_mock_cast_spell_handler(message_sender=message_sender)
        cast_spell_handler.handle.return_value = CommandResult.ok(
            data={"spell_id": 1, "target_x": 53, "target_y": 53, "slot": 1}
        )

        # Target diagonal a 3+3=6 tiles de distancia (Manhattan)
        data = bytes([39, 1, 53, 0, 53, 0, 0])  # X=53, Y=53 + padding
        session_data = {"user_id": 1}

        task = TaskCastSpell(
            data, message_sender, cast_spell_handler=cast_spell_handler, session_data=session_data
        )

        await task.execute()

        # Debe llamar al handler
        cast_spell_handler.handle.assert_called_once()
        call_args = cast_spell_handler.handle.call_args[0][0]
        assert isinstance(call_args, CastSpellCommand)
        assert call_args.target_x == 53
        assert call_args.target_y == 53

    @pytest.mark.asyncio
    async def test_cast_spell_same_position(self) -> None:
        """Test lanzar hechizo en la misma posición del jugador."""
        message_sender = AsyncMock()
        cast_spell_handler = create_mock_cast_spell_handler(message_sender=message_sender)
        cast_spell_handler.handle.return_value = CommandResult.ok(
            data={"spell_id": 1, "target_x": 50, "target_y": 50, "slot": 1}
        )

        # Target en la misma posición (distancia=0)
        data = bytes([39, 1, 50, 0, 50, 0, 0])  # X=50, Y=50 + padding
        session_data = {"user_id": 1}

        task = TaskCastSpell(
            data, message_sender, cast_spell_handler=cast_spell_handler, session_data=session_data
        )

        await task.execute()

        # Debe llamar al handler (distancia 0 es válida)
        cast_spell_handler.handle.assert_called_once()

    @pytest.mark.asyncio
    async def test_cast_spell_max_range(self) -> None:
        """Test lanzar hechizo en el límite del rango máximo."""
        message_sender = AsyncMock()
        cast_spell_handler = create_mock_cast_spell_handler(message_sender=message_sender)
        cast_spell_handler.handle.return_value = CommandResult.ok(
            data={"spell_id": 1, "target_x": 60, "target_y": 50, "slot": 1}
        )

        # Target exactamente a 10 tiles de distancia (límite)
        data = bytes([39, 1, 60, 0, 50, 0, 0])  # X=60, Y=50 + padding
        session_data = {"user_id": 1}

        task = TaskCastSpell(
            data, message_sender, cast_spell_handler=cast_spell_handler, session_data=session_data
        )

        await task.execute()

        # Debe llamar al handler (distancia 10 es válida)
        cast_spell_handler.handle.assert_called_once()

    @pytest.mark.asyncio
    async def test_cast_spell_invalid_packet_size(self) -> None:
        """Test packet CAST_SPELL con tamaño inválido."""
        message_sender = AsyncMock()
        cast_spell_handler = create_mock_cast_spell_handler(message_sender=message_sender)

        # Packet incompleto (solo 1 byte en lugar de al menos 3)
        data = bytes([39])
        session_data = {"user_id": 1}

        task = TaskCastSpell(
            data, message_sender, cast_spell_handler=cast_spell_handler, session_data=session_data
        )

        await task.execute()

        # No debe llamar al handler si el packet es inválido
        cast_spell_handler.handle.assert_not_called()

    @pytest.mark.asyncio
    async def test_cast_spell_old_format(self) -> None:
        """Test lanzar hechizo con formato antiguo (sin coordenadas)."""
        message_sender = AsyncMock()
        cast_spell_handler = create_mock_cast_spell_handler(message_sender=message_sender)
        cast_spell_handler.handle.return_value = CommandResult.ok(
            data={"spell_id": 1, "target_x": 51, "target_y": 50, "slot": 1}
        )

        # Packet formato antiguo (solo 3 bytes)
        data = bytes([39, 1, 0])  # Formato antiguo (3 bytes mínimo)
        session_data = {"user_id": 1}

        task = TaskCastSpell(
            data, message_sender, cast_spell_handler=cast_spell_handler, session_data=session_data
        )

        await task.execute()

        # Debe llamar al handler con target_x y target_y como None
        cast_spell_handler.handle.assert_called_once()
        call_args = cast_spell_handler.handle.call_args[0][0]
        assert isinstance(call_args, CastSpellCommand)
        assert call_args.slot == 1
        assert call_args.target_x is None
        assert call_args.target_y is None
