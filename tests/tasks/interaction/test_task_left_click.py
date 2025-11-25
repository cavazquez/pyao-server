"""Tests para TaskLeftClick."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.commands.base import CommandResult
from src.commands.left_click_command import LeftClickCommand
from src.game.map_manager import MapManager
from src.models.npc import NPC
from src.repositories.player_repository import PlayerRepository
from src.tasks.interaction.task_left_click import TaskLeftClick


def create_mock_left_click_handler(
    map_manager: MapManager | None = None,
    message_sender: MagicMock | None = None,
) -> MagicMock:
    """Crea un mock de LeftClickCommandHandler con las dependencias especificadas."""
    handler = MagicMock()
    handler.map_manager = map_manager or MapManager()
    handler.message_sender = message_sender or MagicMock()
    handler.handle = AsyncMock()
    return handler


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

        left_click_handler = create_mock_left_click_handler(
            map_manager=map_manager, message_sender=message_sender
        )
        left_click_handler.handle.return_value = CommandResult.ok(
            data={"npc_name": "Lobo", "npc_id": 7, "type": "info"}
        )

        task = TaskLeftClick(
            data,
            message_sender,
            left_click_handler=left_click_handler,
            player_repo=player_repo,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert - debe llamar al handler con el comando correcto
        left_click_handler.handle.assert_called_once()
        call_args = left_click_handler.handle.call_args[0][0]
        assert isinstance(call_args, LeftClickCommand)
        assert call_args.user_id == 1
        assert call_args.map_id == 1
        assert call_args.x == 72
        assert call_args.y == 70

    async def test_click_on_empty_position(self) -> None:
        """Test de click en posición vacía."""
        # Setup
        message_sender = MagicMock()
        message_sender.send_console_msg = AsyncMock()

        player_repo = MagicMock(spec=PlayerRepository)
        player_repo.get_position = AsyncMock(return_value={"map": 1, "x": 69, "y": 70})

        map_manager = MapManager()

        left_click_handler = create_mock_left_click_handler(
            map_manager=map_manager, message_sender=message_sender
        )
        left_click_handler.handle.return_value = CommandResult.ok(
            data={
                "type": "tile_info",
                "map_id": 1,
                "x": 50,
                "y": 50,
                "info_lines": ["=== Tile (50, 50) - Mapa 1 ===", "Tile vacio"],
            }
        )

        # Packet: LEFT_CLICK + X=50 + Y=50 (posición vacía)
        data = bytes([0x1A, 50, 50])

        session_data = {"user_id": 1}

        task = TaskLeftClick(
            data,
            message_sender,
            left_click_handler=left_click_handler,
            player_repo=player_repo,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert - debe llamar al handler
        left_click_handler.handle.assert_called_once()

    async def test_click_without_session(self) -> None:
        """Test de click sin sesión activa."""
        # Setup
        message_sender = MagicMock()
        player_repo = MagicMock(spec=PlayerRepository)
        MapManager()

        data = bytes([0x1A, 50, 50])
        session_data = {}  # Sin user_id

        left_click_handler = create_mock_left_click_handler()

        task = TaskLeftClick(
            data,
            message_sender,
            left_click_handler=left_click_handler,
            player_repo=player_repo,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert - no debe llamar al handler sin sesión
        left_click_handler.handle.assert_not_called()

    async def test_click_on_friendly_npc(self) -> None:
        """Test de click en NPC amigable."""
        # Setup
        message_sender = MagicMock()
        message_sender.send_console_msg = AsyncMock()

        player_repo = MagicMock(spec=PlayerRepository)
        player_repo.get_position = AsyncMock(return_value={"map": 1, "x": 69, "y": 70})

        map_manager = MapManager()

        left_click_handler = create_mock_left_click_handler(
            map_manager=map_manager, message_sender=message_sender
        )
        left_click_handler.handle.return_value = CommandResult.ok(
            data={"npc_name": "Comerciante", "npc_id": 2, "type": "info"}
        )

        data = bytes([0x1A, 69, 67])
        session_data = {"user_id": 1}

        task = TaskLeftClick(
            data,
            message_sender,
            left_click_handler=left_click_handler,
            player_repo=player_repo,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert - debe llamar al handler
        left_click_handler.handle.assert_called_once()

    async def test_invalid_packet_size(self) -> None:
        """Test con packet de tamaño inválido."""
        # Setup
        message_sender = AsyncMock()
        player_repo = MagicMock(spec=PlayerRepository)
        MapManager()

        # Packet muy corto
        data = bytes([0x1A, 50])  # Falta Y

        session_data = {"user_id": 1}

        left_click_handler = create_mock_left_click_handler()

        task = TaskLeftClick(
            data,
            message_sender,
            left_click_handler=left_click_handler,
            player_repo=player_repo,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert - no debe llamar al handler con packet inválido
        left_click_handler.handle.assert_not_called()
        # Debe enviar mensaje de error
        message_sender.send_console_msg.assert_called_once()
