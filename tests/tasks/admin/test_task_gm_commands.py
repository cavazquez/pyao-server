"""Tests básicos para TaskGMCommands (comandos de Game Master)."""

import struct
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.network.packet_id import ClientPacketID
from src.tasks.admin.task_gm_commands import TaskGMCommands


@pytest.fixture
def mock_message_sender():
    """Mock de message_sender con métodos async."""
    sender = MagicMock()
    sender.console.send_console_msg = AsyncMock()
    sender.console.send_error_msg = AsyncMock()
    sender.send_change_map = AsyncMock()
    sender.send_pos_update = AsyncMock()
    sender.send_character_create = AsyncMock()
    return sender


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

        task = TaskGMCommands(
            packet,
            mock_message_sender,
            player_repo=AsyncMock(),
            map_manager=MagicMock(),
            broadcast_service=AsyncMock(),
            player_map_service=AsyncMock(),
            session_data={},  # Sin user_id
        )
        await task.execute()

        # No debe crashear, solo retornar early
        # El código loguea pero no envía mensaje al cliente

    @pytest.mark.asyncio
    async def test_gm_command_without_repositories(self, mock_message_sender):
        """Test sin repositorios retorna sin ejecutar."""
        packet = self._create_gm_packet()

        task = TaskGMCommands(
            packet,
            mock_message_sender,
            player_repo=None,  # Sin repo
            map_manager=None,
            broadcast_service=None,
            player_map_service=None,
            session_data={"user_id": 1},
        )
        await task.execute()

        # No debe crashear, solo retornar early
        # El código loguea pero no envía mensaje al cliente

    @pytest.mark.asyncio
    async def test_gm_command_task_creation(self, mock_message_sender):
        """Test que la task se puede crear con todas las dependencias."""
        packet = self._create_gm_packet()

        task = TaskGMCommands(
            packet,
            mock_message_sender,
            player_repo=AsyncMock(),
            map_manager=MagicMock(),
            broadcast_service=AsyncMock(),
            player_map_service=AsyncMock(),
            session_data={"user_id": 1},
        )

        # Verificar que la task se creó correctamente
        assert task is not None
        assert task.data == packet
        assert task.message_sender == mock_message_sender
        assert task.player_repo is not None
        assert task.map_manager is not None

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
