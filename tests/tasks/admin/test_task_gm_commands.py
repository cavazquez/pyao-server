"""Tests básicos para TaskGMCommands (comandos de Game Master)."""

import struct
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.commands.base import CommandResult
from src.commands.gm_command import GMCommand
from src.network.packet_id import ClientPacketID
from src.tasks.admin.task_gm_commands import TaskGMCommands


@pytest.fixture
def mock_message_sender():
    """Mock de message_sender con métodos async."""
    sender = MagicMock()
    sender.connection = MagicMock()
    sender.connection.address = ("127.0.0.1", 12345)
    sender.send_console_msg = AsyncMock()
    sender.send_change_map = AsyncMock()
    sender.send_pos_update = AsyncMock()
    sender.send_character_create = AsyncMock()
    return sender


def create_mock_gm_command_handler(
    player_repo: MagicMock | None = None,
    player_map_service: MagicMock | None = None,
    message_sender: MagicMock | None = None,
) -> MagicMock:
    """Crea un mock de GMCommandHandler."""
    handler = MagicMock()
    handler.player_repo = player_repo or MagicMock()
    handler.player_map_service = player_map_service or MagicMock()
    handler.message_sender = message_sender or MagicMock()
    handler.handle = AsyncMock()
    return handler


class TestTaskGMCommands:
    """Tests para TaskGMCommands."""

    def _create_gm_packet(self, subcommand: int = 11) -> bytes:
        """Crea un packet GM_COMMANDS básico."""
        # Formato: PacketID + Subcomando + Username (length + bytes) + map + x + y
        username = "YO"
        username_bytes = username.encode("utf-16-le")
        username_len = len(username_bytes)

        return struct.pack(
            f"<BBH{username_len}sHBB",
            ClientPacketID.GM_COMMANDS,
            subcommand,
            username_len,
            username_bytes,
            1,  # map_id
            50,  # x
            50,  # y
        )

    @pytest.mark.asyncio
    async def test_gm_command_without_session(self, mock_message_sender):
        """Test sin sesión activa retorna sin ejecutar."""
        packet = self._create_gm_packet()

        gm_command_handler = create_mock_gm_command_handler()

        task = TaskGMCommands(
            packet,
            mock_message_sender,
            gm_command_handler=gm_command_handler,
            session_data={},  # Sin user_id
        )
        await task.execute()

        # No debe llamar al handler sin sesión
        gm_command_handler.handle.assert_not_called()

    @pytest.mark.asyncio
    async def test_gm_command_without_handler(self, mock_message_sender):
        """Test sin handler retorna sin ejecutar."""
        packet = self._create_gm_packet()

        task = TaskGMCommands(
            packet,
            mock_message_sender,
            gm_command_handler=None,
            session_data={"user_id": 1},
        )
        await task.execute()

        # No debe crashear, solo retornar early

    @pytest.mark.asyncio
    async def test_gm_command_task_creation(self, mock_message_sender):
        """Test que la task se puede crear con todas las dependencias."""
        packet = self._create_gm_packet()

        gm_command_handler = create_mock_gm_command_handler()

        task = TaskGMCommands(
            packet,
            mock_message_sender,
            gm_command_handler=gm_command_handler,
            session_data={"user_id": 1},
        )

        # Verificar que la task se creó correctamente
        assert task is not None
        assert task.data == packet
        assert task.message_sender == mock_message_sender

    @pytest.mark.asyncio
    async def test_gm_command_packet_structure(self):
        """Test que el packet GM tiene la estructura esperada."""
        packet = self._create_gm_packet(subcommand=11)

        # Verificar estructura básica
        assert packet[0] == ClientPacketID.GM_COMMANDS
        assert packet[1] == 11  # Subcomando
        assert len(packet) > 4  # Tiene más datos

    @pytest.mark.asyncio
    async def test_gm_command_different_subcommands(self):
        """Test que diferentes subcomandos crean packets diferentes."""
        packet1 = self._create_gm_packet(subcommand=11)
        packet2 = self._create_gm_packet(subcommand=12)

        # El subcomando debe ser diferente
        assert packet1[1] != packet2[1]

    @pytest.mark.asyncio
    async def test_gm_command_execute_success(self, mock_message_sender):
        """Test ejecución exitosa de comando GM."""
        packet = self._create_gm_packet()

        player_repo = MagicMock()
        player_repo.get_position = AsyncMock(
            return_value={"map": 1, "x": 10, "y": 10, "heading": 3}
        )

        player_map_service = MagicMock()
        player_map_service.teleport_in_same_map = AsyncMock()

        gm_command_handler = create_mock_gm_command_handler(
            player_repo=player_repo,
            player_map_service=player_map_service,
            message_sender=mock_message_sender,
        )
        gm_command_handler.handle.return_value = CommandResult.ok(
            data={
                "user_id": 1,
                "from_map": 1,
                "from_x": 10,
                "from_y": 10,
                "to_map": 1,
                "to_x": 50,
                "to_y": 50,
            }
        )

        task = TaskGMCommands(
            packet,
            mock_message_sender,
            gm_command_handler=gm_command_handler,
            session_data={"user_id": 1},
        )

        await task.execute()

        # Debe llamar al handler con el comando correcto
        gm_command_handler.handle.assert_called_once()
        call_args = gm_command_handler.handle.call_args[0][0]
        assert isinstance(call_args, GMCommand)
        assert call_args.user_id == 1
        assert call_args.subcommand == 11
        assert call_args.username == "YO"
        assert call_args.map_id == 1
        assert call_args.x == 50
        assert call_args.y == 50
