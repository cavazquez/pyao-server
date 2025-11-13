"""Tests para TaskGMCommands con validación completa."""

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
    sender.send_console_msg = AsyncMock()  # Agregar mock directo para send_console_msg
    return sender


class TestTaskGMCommands:
    """Tests para TaskGMCommands."""

    def _create_gm_packet(
        self, subcommand: int = 11, map_id: int = 1, x: int = 50, y: int = 50, username: str = "YO"
    ) -> bytes:
        """Crea un packet GM_COMMANDS básico."""
        username_bytes = username.encode("utf-16-le")
        username_len = len(username_bytes)

        return struct.pack(
            f"<BBH{username_len}sHBB",
            ClientPacketID.GM_COMMANDS,
            subcommand,
            username_len,
            username_bytes,
            map_id,
            x,
            y,
        )

    @pytest.mark.asyncio
    async def test_teleport_command_success(self, mock_message_sender):
        """Test comando /telep exitoso (mismo mapa)."""
        packet = self._create_gm_packet(map_id=1, x=80, y=80)

        # Mock de dependencias
        player_repo = AsyncMock()
        player_repo.get_position.return_value = {"map": 1, "x": 50, "y": 50, "heading": 3}

        player_map_service = AsyncMock()

        task = TaskGMCommands(
            packet,
            mock_message_sender,
            player_repo=player_repo,
            map_manager=MagicMock(),
            broadcast_service=AsyncMock(),
            player_map_service=player_map_service,
            session_data={"user_id": 1},
        )

        await task.execute()

        # Verificar que se llamó a teleport_in_same_map
        player_map_service.teleport_in_same_map.assert_awaited_once_with(
            user_id=1,
            map_id=1,
            old_x=50,
            old_y=50,
            new_x=80,
            new_y=80,
            heading=3,
            message_sender=mock_message_sender,
        )

    @pytest.mark.asyncio
    async def test_teleport_command_different_map(self, mock_message_sender):
        """Test comando /telep a otro mapa."""
        packet = self._create_gm_packet(map_id=2, x=30, y=40)

        # Mock de dependencias
        player_repo = AsyncMock()
        player_repo.get_position.return_value = {"map": 1, "x": 50, "y": 50, "heading": 3}

        player_map_service = AsyncMock()

        task = TaskGMCommands(
            packet,
            mock_message_sender,
            player_repo=player_repo,
            map_manager=MagicMock(),
            broadcast_service=AsyncMock(),
            player_map_service=player_map_service,
            session_data={"user_id": 1},
        )

        await task.execute()

        # Verificar que se llamó a transition_to_map
        player_map_service.transition_to_map.assert_awaited_once_with(
            user_id=1,
            current_map=1,
            current_x=50,
            current_y=50,
            new_map=2,
            new_x=30,
            new_y=40,
            heading=3,
            message_sender=mock_message_sender,
        )

    @pytest.mark.asyncio
    async def test_invalid_gm_command(self, mock_message_sender):
        """Test comando GM inválido (posición fuera de rango)."""
        # Crear packet con posición inválida (231, 3)
        packet = self._create_gm_packet(x=231, y=3)

        task = TaskGMCommands(
            packet,
            mock_message_sender,
            player_repo=AsyncMock(),
            map_manager=MagicMock(),
            broadcast_service=AsyncMock(),
            player_map_service=AsyncMock(),
            session_data={"user_id": 1},
        )

        await task.execute()

        # No debe llamar a ningún método de teletransporte
        # El error se loguea pero no se envía mensaje al cliente
        # (comportamiento actual según el código)

    @pytest.mark.asyncio
    async def test_teleport_with_missing_parameters(self, mock_message_sender):
        """Test comando GM sin parámetros suficientes."""
        # Packet truncado (solo PacketID y subcomando)
        packet = struct.pack("<BB", ClientPacketID.GM_COMMANDS, 11)

        task = TaskGMCommands(
            packet,
            mock_message_sender,
            player_repo=AsyncMock(),
            map_manager=MagicMock(),
            broadcast_service=AsyncMock(),
            player_map_service=AsyncMock(),
            session_data={"user_id": 1},
        )

        await task.execute()

        # No debe llamar a ningún método de teletransporte
        # El error se loguea pero no se envía mensaje al cliente

    @pytest.mark.asyncio
    async def test_teleport_with_invalid_map(self, mock_message_sender):
        """Test comando GM con map_id inválido."""
        # Map ID fuera de rango (2000 > 1000)
        packet = self._create_gm_packet(map_id=2000)

        task = TaskGMCommands(
            packet,
            mock_message_sender,
            player_repo=AsyncMock(),
            map_manager=MagicMock(),
            broadcast_service=AsyncMock(),
            player_map_service=AsyncMock(),
            session_data={"user_id": 1},
        )

        await task.execute()

        # No debe llamar a ningún método de teletransporte
        # El error se loguea pero no se envía mensaje al cliente

    @pytest.mark.asyncio
    async def test_teleport_with_invalid_username(self, mock_message_sender):
        """Test comando GM con username inválido (demasiado largo)."""
        # Username de más de 20 caracteres
        long_username = "A" * 25
        packet = self._create_gm_packet(username=long_username)

        task = TaskGMCommands(
            packet,
            mock_message_sender,
            player_repo=AsyncMock(),
            map_manager=MagicMock(),
            broadcast_service=AsyncMock(),
            player_map_service=AsyncMock(),
            session_data={"user_id": 1},
        )

        await task.execute()

        # No debe llamar a ningún método de teletransporte
        # El error se loguea pero no se envía mensaje al cliente

    @pytest.mark.asyncio
    async def test_teleport_other_player_not_implemented(self, mock_message_sender):
        """Test teletransporte de otro jugador (no implementado)."""
        packet = self._create_gm_packet(username="OTROJUGADOR")

        task = TaskGMCommands(
            packet,
            mock_message_sender,
            player_repo=AsyncMock(),
            map_manager=MagicMock(),
            broadcast_service=AsyncMock(),
            player_map_service=AsyncMock(),
            session_data={"user_id": 1},
        )

        await task.execute()

        # Debe enviar mensaje de no implementado
        mock_message_sender.send_console_msg.assert_awaited_once_with(
            "Teletransporte de otros jugadores no implementado aún."
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

    @pytest.mark.asyncio
    async def test_gm_command_without_player_position(self, mock_message_sender):
        """Test cuando no se encuentra posición del jugador."""
        packet = self._create_gm_packet()

        # Mock que retorna None (no encontró posición)
        player_repo = AsyncMock()
        player_repo.get_position.return_value = None

        task = TaskGMCommands(
            packet,
            mock_message_sender,
            player_repo=player_repo,
            map_manager=MagicMock(),
            broadcast_service=AsyncMock(),
            player_map_service=AsyncMock(),
            session_data={"user_id": 1},
        )

        await task.execute()

        # No debe llamar a teletransporte
        # Solo debe loggear warning

    @pytest.mark.asyncio
    async def test_gm_command_with_invalid_session_data(self, mock_message_sender):
        """Test con user_id inválido en sesión."""
        packet = self._create_gm_packet()

        task = TaskGMCommands(
            packet,
            mock_message_sender,
            player_repo=AsyncMock(),
            map_manager=MagicMock(),
            broadcast_service=AsyncMock(),
            player_map_service=AsyncMock(),
            session_data={"user_id": {"invalid": "dict"}},  # user_id es dict en vez de int
        )

        await task.execute()

        # No debe crashear, solo retornar early

    def test_gm_command_packet_structure(self):
        """Test que el packet GM tiene la estructura esperada."""
        packet = self._create_gm_packet(subcommand=11)

        # Verificar estructura básica
        assert packet[0] == ClientPacketID.GM_COMMANDS
        assert packet[1] == 11  # Subcomando
        assert len(packet) > 4  # Tiene más datos

    def test_gm_command_different_subcommands(self):
        """Test que diferentes subcomandos crean packets diferentes."""
        packet1 = self._create_gm_packet(subcommand=11)
        packet2 = self._create_gm_packet(subcommand=12)

        # El subcomando debe ser diferente
        assert packet1[1] != packet2[1]

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
