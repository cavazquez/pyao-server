"""Tests para TaskLeftClick."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.map_manager import MapManager
from src.npc import NPC
from src.player_repository import PlayerRepository
from src.task_left_click import TaskLeftClick


@pytest.mark.asyncio
class TestTaskLeftClick:
    """Tests para TaskLeftClick."""

    async def test_click_on_npc(self) -> None:
        """Test de click en un NPC existente."""
        # Setup
        message_sender = MagicMock()
        message_sender.send_console_msg = AsyncMock()

        player_repo = MagicMock(spec=PlayerRepository)
        player_repo.get_position = AsyncMock(return_value={"map": 1, "x": 69, "y": 70})

        map_manager = MapManager()

        # Crear un NPC en posición (72, 70)
        npc = NPC(
            npc_id=7,
            char_index=10001,
            instance_id="test-lobo",
            map_id=1,
            x=72,
            y=70,
            heading=4,
            name="Lobo",
            description="Un lobo salvaje",
            body_id=138,
            head_id=0,
            hp=80,
            max_hp=80,
            level=3,
            is_hostile=True,
            is_attackable=True,
            movement_type="static",
            respawn_time=0,
            respawn_time_max=0,
            gold_min=5,
            gold_max=20,
        )
        map_manager.add_npc(1, npc)

        # Packet: LEFT_CLICK (0x1A) + X=72 + Y=70
        data = bytes([0x1A, 72, 70])

        session_data = {"user_id": 1}

        task = TaskLeftClick(data, message_sender, player_repo, map_manager, session_data)

        # Execute
        await task.execute()

        # Assert
        message_sender.send_console_msg.assert_called_once()
        call_args = message_sender.send_console_msg.call_args[0][0]
        assert "Lobo" in call_args
        assert "Nivel 3" in call_args
        assert "Hostil" in call_args
        assert "HP: 80/80" in call_args

    async def test_click_on_empty_position(self) -> None:
        """Test de click en posición vacía."""
        # Setup
        message_sender = MagicMock()
        message_sender.send_console_msg = AsyncMock()

        player_repo = MagicMock(spec=PlayerRepository)
        player_repo.get_position = AsyncMock(return_value={"map": 1, "x": 69, "y": 70})

        map_manager = MapManager()

        # Packet: LEFT_CLICK + X=50 + Y=50 (posición vacía)
        data = bytes([0x1A, 50, 50])

        session_data = {"user_id": 1}

        task = TaskLeftClick(data, message_sender, player_repo, map_manager, session_data)

        # Execute
        await task.execute()

        # Assert
        message_sender.send_console_msg.assert_called_once()
        call_args = message_sender.send_console_msg.call_args[0][0]
        assert "No hay nadie" in call_args

    async def test_click_without_session(self) -> None:
        """Test de click sin sesión activa."""
        # Setup
        message_sender = MagicMock()
        player_repo = MagicMock(spec=PlayerRepository)
        map_manager = MapManager()

        data = bytes([0x1A, 50, 50])
        session_data = {}  # Sin user_id

        task = TaskLeftClick(data, message_sender, player_repo, map_manager, session_data)

        # Execute
        await task.execute()

        # Assert - no debe enviar mensajes
        message_sender.send_console_msg.assert_not_called()

    async def test_click_on_friendly_npc(self) -> None:
        """Test de click en NPC amigable."""
        # Setup
        message_sender = MagicMock()
        message_sender.send_console_msg = AsyncMock()

        player_repo = MagicMock(spec=PlayerRepository)
        player_repo.get_position = AsyncMock(return_value={"map": 1, "x": 69, "y": 70})

        map_manager = MapManager()

        # Crear NPC amigable
        npc = NPC(
            npc_id=2,
            char_index=10002,
            instance_id="test-comerciante",
            map_id=1,
            x=69,
            y=67,
            heading=3,
            name="Comerciante",
            description="Vende items",
            body_id=501,
            head_id=1,
            hp=0,
            max_hp=0,
            level=0,
            is_hostile=False,
            is_attackable=False,
            movement_type="static",
            respawn_time=0,
            respawn_time_max=0,
            gold_min=0,
            gold_max=0,
        )
        map_manager.add_npc(1, npc)

        data = bytes([0x1A, 69, 67])
        session_data = {"user_id": 1}

        task = TaskLeftClick(data, message_sender, player_repo, map_manager, session_data)

        # Execute
        await task.execute()

        # Assert
        message_sender.send_console_msg.assert_called_once()
        call_args = message_sender.send_console_msg.call_args[0][0]
        assert "Comerciante" in call_args
        assert "Amigable" in call_args

    async def test_invalid_packet_size(self) -> None:
        """Test con packet de tamaño inválido."""
        # Setup
        message_sender = MagicMock()
        player_repo = MagicMock(spec=PlayerRepository)
        map_manager = MapManager()

        # Packet muy corto
        data = bytes([0x1A, 50])  # Falta Y

        session_data = {"user_id": 1}

        task = TaskLeftClick(data, message_sender, player_repo, map_manager, session_data)

        # Execute
        await task.execute()

        # Assert - no debe crashear
        message_sender.send_console_msg.assert_not_called()
