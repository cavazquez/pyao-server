"""Tests para TaskDoubleClick."""

import struct
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.commands.base import CommandResult
from src.commands.double_click_command import DoubleClickCommand
from src.game.map_manager import MapManager
from src.models.npc import NPC
from src.network.packet_id import ClientPacketID
from src.repositories.player_repository import PlayerRepository
from src.tasks.inventory.task_double_click import TaskDoubleClick


def create_mock_double_click_handler(
    player_repo: MagicMock | None = None,
    map_manager: MapManager | None = None,
    message_sender: MagicMock | None = None,
) -> MagicMock:
    """Crea un mock de DoubleClickCommandHandler con las dependencias especificadas."""
    handler = MagicMock()
    handler.player_repo = player_repo or MagicMock()
    handler.map_manager = map_manager or MagicMock()
    handler.message_sender = message_sender or MagicMock()
    handler.handle = AsyncMock()
    return handler


@pytest.mark.asyncio
class TestTaskDoubleClick:
    """Tests para TaskDoubleClick."""

    async def test_double_click_detects_item_vs_npc(self) -> None:
        """Test de que detecta correctamente item vs NPC por el valor del target."""
        # Test 1: Target < 100 debe intentar usar item
        data_item = bytes([ClientPacketID.DOUBLE_CLICK, 5])  # slot=5 < 100
        target = struct.unpack("B", data_item[1:2])[0]
        assert target < 100  # Es un item

        # Test 2: Target > 100 debe buscar NPC
        data_npc = bytes([ClientPacketID.DOUBLE_CLICK, 150])  # CharIndex=150 > 100
        target_npc = struct.unpack("B", data_npc[1:2])[0]
        assert target_npc > 100  # Es un NPC

    async def test_double_click_on_hostile_npc(self) -> None:
        """Test de doble click en NPC hostil."""
        # Setup
        message_sender = AsyncMock()

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
        data = bytes([ClientPacketID.DOUBLE_CLICK, 150])

        session_data = {"user_id": 1}

        double_click_handler = create_mock_double_click_handler(
            player_repo=player_repo, map_manager=map_manager, message_sender=message_sender
        )
        double_click_handler.handle.return_value = CommandResult.ok(
            data={"npc_name": "Lobo", "char_index": 150, "is_hostile": True}
        )

        task = TaskDoubleClick(
            data,
            message_sender,
            double_click_handler=double_click_handler,
            player_repo=player_repo,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert - debe llamar al handler con el comando correcto
        double_click_handler.handle.assert_called_once()
        call_args = double_click_handler.handle.call_args[0][0]
        assert isinstance(call_args, DoubleClickCommand)
        assert call_args.user_id == 1
        assert call_args.target == 150
        assert call_args.map_id == 1

    async def test_double_click_on_friendly_npc(self) -> None:
        """Test de doble click en NPC amigable."""
        # Setup
        message_sender = AsyncMock()

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
        data = bytes([ClientPacketID.DOUBLE_CLICK, 120])

        session_data = {"user_id": 1}

        double_click_handler = create_mock_double_click_handler(
            player_repo=player_repo, map_manager=map_manager, message_sender=message_sender
        )
        double_click_handler.handle.return_value = CommandResult.ok(
            data={"npc_name": "Comerciante", "char_index": 120, "is_hostile": False}
        )

        task = TaskDoubleClick(
            data,
            message_sender,
            double_click_handler=double_click_handler,
            player_repo=player_repo,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert - debe llamar al handler
        double_click_handler.handle.assert_called_once()
        call_args = double_click_handler.handle.call_args[0][0]
        assert isinstance(call_args, DoubleClickCommand)
        assert call_args.target == 120

    async def test_double_click_without_session(self) -> None:
        """Test de doble click sin sesión activa."""
        # Setup
        message_sender = AsyncMock()
        player_repo = MagicMock(spec=PlayerRepository)
        MapManager()

        data = bytes([ClientPacketID.DOUBLE_CLICK, 5])
        session_data = {}  # Sin user_id

        double_click_handler = create_mock_double_click_handler()

        task = TaskDoubleClick(
            data,
            message_sender,
            double_click_handler=double_click_handler,
            player_repo=player_repo,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert - no debe llamar al handler
        double_click_handler.handle.assert_not_called()

    async def test_double_click_on_nonexistent_npc(self) -> None:
        """Test de doble click en NPC que no existe."""
        # Setup
        message_sender = AsyncMock()

        player_repo = MagicMock(spec=PlayerRepository)
        player_repo.get_position = AsyncMock(return_value={"map": 1, "x": 69, "y": 70})

        map_manager = MapManager()  # Sin NPCs

        # Packet: DOUBLE_CLICK + CharIndex=150 (NPC inexistente)
        data = bytes([ClientPacketID.DOUBLE_CLICK, 150])

        session_data = {"user_id": 1}

        double_click_handler = create_mock_double_click_handler(
            player_repo=player_repo, map_manager=map_manager, message_sender=message_sender
        )
        double_click_handler.handle.return_value = CommandResult.error("No hay nadie ahí")

        task = TaskDoubleClick(
            data,
            message_sender,
            double_click_handler=double_click_handler,
            player_repo=player_repo,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert - debe llamar al handler
        double_click_handler.handle.assert_called_once()

    async def test_invalid_packet_size(self) -> None:
        """Test con packet de tamaño inválido."""
        # Setup
        message_sender = AsyncMock()
        player_repo = MagicMock(spec=PlayerRepository)
        MapManager()

        # Packet muy corto
        data = bytes([ClientPacketID.DOUBLE_CLICK])  # Falta el target

        session_data = {"user_id": 1}

        double_click_handler = create_mock_double_click_handler()

        task = TaskDoubleClick(
            data,
            message_sender,
            double_click_handler=double_click_handler,
            player_repo=player_repo,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert - debe enviar mensaje de error y no llamar al handler
        message_sender.send_console_msg.assert_called_once()
        double_click_handler.handle.assert_not_called()
