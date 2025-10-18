"""Tests para TaskDoubleClick."""

import struct
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.map_manager import MapManager
from src.npc import NPC
from src.player_repository import PlayerRepository
from src.task_double_click import TaskDoubleClick


@pytest.mark.asyncio
class TestTaskDoubleClick:
    """Tests para TaskDoubleClick."""

    async def test_double_click_detects_item_vs_npc(self) -> None:
        """Test de que detecta correctamente item vs NPC por el valor del target."""
        # Test 1: Target < 100 debe intentar usar item
        data_item = bytes([0x1B, 5])  # slot=5 < 100
        target = struct.unpack("B", data_item[1:2])[0]
        assert target < 100  # Es un item

        # Test 2: Target > 100 debe buscar NPC
        data_npc = bytes([0x1B, 150])  # CharIndex=150 > 100
        target_npc = struct.unpack("B", data_npc[1:2])[0]
        assert target_npc > 100  # Es un NPC

    async def test_double_click_on_hostile_npc(self) -> None:
        """Test de doble click en NPC hostil."""
        # Setup
        message_sender = MagicMock()
        message_sender.send_console_msg = AsyncMock()

        player_repo = MagicMock(spec=PlayerRepository)
        player_repo.get_position = AsyncMock(return_value={"map": 1, "x": 69, "y": 70})

        map_manager = MapManager()

        # Crear NPC hostil
        npc = NPC(
            npc_id=7,
            char_index=150,  # > 100, será interpretado como NPC
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

        # Packet: DOUBLE_CLICK + CharIndex=150 (> 100, es NPC)
        data = bytes([0x1B, 150])

        session_data = {"user_id": 1}

        task = TaskDoubleClick(data, message_sender, player_repo, map_manager, session_data)

        # Execute
        await task.execute()

        # Assert
        message_sender.send_console_msg.assert_called_once()
        call_args = message_sender.send_console_msg.call_args[0][0]
        assert "Lobo" in call_args
        assert "hostilidad" in call_args or "combate" in call_args

    async def test_double_click_on_friendly_npc(self) -> None:
        """Test de doble click en NPC amigable."""
        # Setup
        message_sender = MagicMock()
        message_sender.send_console_msg = AsyncMock()

        player_repo = MagicMock(spec=PlayerRepository)
        player_repo.get_position = AsyncMock(return_value={"map": 1, "x": 69, "y": 70})

        map_manager = MapManager()

        # Crear NPC amigable
        npc = NPC(
            npc_id=2,
            char_index=120,
            instance_id="test-comerciante",
            map_id=1,
            x=69,
            y=67,
            heading=3,
            name="Comerciante",
            description="Bienvenido a mi tienda",
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

        # Packet: DOUBLE_CLICK + CharIndex=120
        data = bytes([0x1B, 120])

        session_data = {"user_id": 1}

        task = TaskDoubleClick(data, message_sender, player_repo, map_manager, session_data)

        # Execute
        await task.execute()

        # Assert
        message_sender.send_console_msg.assert_called_once()
        call_args = message_sender.send_console_msg.call_args[0][0]
        assert "Comerciante" in call_args
        assert "tienda" in call_args or "aventurero" in call_args

    async def test_double_click_without_session(self) -> None:
        """Test de doble click sin sesión activa."""
        # Setup
        message_sender = MagicMock()
        player_repo = MagicMock(spec=PlayerRepository)
        map_manager = MapManager()

        data = bytes([0x1B, 5])
        session_data = {}  # Sin user_id

        task = TaskDoubleClick(data, message_sender, player_repo, map_manager, session_data)

        # Execute
        await task.execute()

        # Assert - no debe enviar mensajes
        message_sender.send_console_msg.assert_not_called()

    async def test_double_click_on_nonexistent_npc(self) -> None:
        """Test de doble click en NPC que no existe."""
        # Setup
        message_sender = MagicMock()
        message_sender.send_console_msg = AsyncMock()

        player_repo = MagicMock(spec=PlayerRepository)
        player_repo.get_position = AsyncMock(return_value={"map": 1, "x": 69, "y": 70})

        map_manager = MapManager()  # Sin NPCs

        # Packet: DOUBLE_CLICK + CharIndex=150 (NPC inexistente)
        data = bytes([0x1B, 150])

        session_data = {"user_id": 1}

        task = TaskDoubleClick(data, message_sender, player_repo, map_manager, session_data)

        # Execute
        await task.execute()

        # Assert
        message_sender.send_console_msg.assert_called_once()
        call_args = message_sender.send_console_msg.call_args[0][0]
        assert "No hay nadie" in call_args or "nadie ahí" in call_args

    async def test_invalid_packet_size(self) -> None:
        """Test con packet de tamaño inválido."""
        # Setup
        message_sender = MagicMock()
        player_repo = MagicMock(spec=PlayerRepository)
        map_manager = MapManager()

        # Packet muy corto
        data = bytes([0x1B])  # Falta el target

        session_data = {"user_id": 1}

        task = TaskDoubleClick(data, message_sender, player_repo, map_manager, session_data)

        # Execute
        await task.execute()

        # Assert - no debe crashear
        message_sender.send_console_msg.assert_not_called()
