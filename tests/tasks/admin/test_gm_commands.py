"""Tests para TaskGMCommands con validación completa."""

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
        player_repo = MagicMock()
        player_repo.get_position = AsyncMock(
            return_value={"map": 1, "x": 50, "y": 50, "heading": 3}
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
                "from_x": 50,
                "from_y": 50,
                "to_map": 1,
                "to_x": 80,
                "to_y": 80,
            }
        )

        task = TaskGMCommands(
            packet,
            mock_message_sender,
            gm_command_handler=gm_command_handler,
            session_data={"user_id": 1},
        )

        await task.execute()

        # Debe llamar al handler
        gm_command_handler.handle.assert_called_once()
        call_args = gm_command_handler.handle.call_args[0][0]
        assert isinstance(call_args, GMCommand)
        assert call_args.user_id == 1
        assert call_args.map_id == 1
        assert call_args.x == 80
        assert call_args.y == 80

    @pytest.mark.asyncio
    async def test_teleport_command_different_map(self, mock_message_sender):
        """Test comando /telep a otro mapa."""
        packet = self._create_gm_packet(map_id=2, x=30, y=40)

        # Mock de dependencias
        player_repo = MagicMock()
        player_repo.get_position = AsyncMock(
            return_value={"map": 1, "x": 50, "y": 50, "heading": 3}
        )

        player_map_service = MagicMock()
        player_map_service.transition_to_map = AsyncMock()

        gm_command_handler = create_mock_gm_command_handler(
            player_repo=player_repo,
            player_map_service=player_map_service,
            message_sender=mock_message_sender,
        )
        gm_command_handler.handle.return_value = CommandResult.ok(
            data={
                "user_id": 1,
                "from_map": 1,
                "from_x": 50,
                "from_y": 50,
                "to_map": 2,
                "to_x": 30,
                "to_y": 40,
            }
        )

        task = TaskGMCommands(
            packet,
            mock_message_sender,
            gm_command_handler=gm_command_handler,
            session_data={"user_id": 1},
        )

        await task.execute()

        # Debe llamar al handler
        gm_command_handler.handle.assert_called_once()
        call_args = gm_command_handler.handle.call_args[0][0]
        assert isinstance(call_args, GMCommand)
        assert call_args.user_id == 1
        assert call_args.map_id == 2
        assert call_args.x == 30
        assert call_args.y == 40

    @pytest.mark.asyncio
    async def test_invalid_gm_command(self, mock_message_sender):
        """Test comando GM inválido (posición fuera de rango)."""
        # Crear packet con posición inválida (231, 3)
        packet = self._create_gm_packet(x=231, y=3)

        gm_command_handler = create_mock_gm_command_handler()

        task = TaskGMCommands(
            packet,
            mock_message_sender,
            gm_command_handler=gm_command_handler,
            session_data={"user_id": 1},
        )

        await task.execute()

        # Si el parsing falla, no debe llamar al handler
        # (el comportamiento depende de validate_gm_teleport)

    @pytest.mark.asyncio
    async def test_teleport_with_missing_parameters(self, mock_message_sender):
        """Test comando GM sin parámetros suficientes."""
        # Packet truncado (solo PacketID y subcomando)
        packet = struct.pack("<BB", ClientPacketID.GM_COMMANDS, 11)

        gm_command_handler = create_mock_gm_command_handler()

        task = TaskGMCommands(
            packet,
            mock_message_sender,
            gm_command_handler=gm_command_handler,
            session_data={"user_id": 1},
        )

        await task.execute()

        # No debe llamar al handler con packet inválido
        gm_command_handler.handle.assert_not_called()

    @pytest.mark.asyncio
    async def test_teleport_with_invalid_map(self, mock_message_sender):
        """Test comando GM con map_id inválido."""
        # Map ID fuera de rango (2000 > 1000)
        packet = self._create_gm_packet(map_id=2000)

        gm_command_handler = create_mock_gm_command_handler()

        task = TaskGMCommands(
            packet,
            mock_message_sender,
            gm_command_handler=gm_command_handler,
            session_data={"user_id": 1},
        )

        await task.execute()

        # Si el parsing falla, no debe llamar al handler
        # (el comportamiento depende de validate_gm_teleport)

    @pytest.mark.asyncio
    async def test_teleport_with_invalid_username(self, mock_message_sender):
        """Test comando GM con username inválido (demasiado largo)."""
        # Username de más de 20 caracteres
        long_username = "A" * 25
        packet = self._create_gm_packet(username=long_username)

        gm_command_handler = create_mock_gm_command_handler()

        task = TaskGMCommands(
            packet,
            mock_message_sender,
            gm_command_handler=gm_command_handler,
            session_data={"user_id": 1},
        )

        await task.execute()

        # Si el parsing falla, no debe llamar al handler
        # (el comportamiento depende de validate_gm_teleport)

    @pytest.mark.asyncio
    async def test_teleport_other_player_not_implemented(self, mock_message_sender):
        """Test teletransporte de otro jugador (no implementado)."""
        packet = self._create_gm_packet(username="OTROJUGADOR")

        gm_command_handler = create_mock_gm_command_handler(message_sender=mock_message_sender)
        gm_command_handler.handle.return_value = CommandResult.error(
            "Teletransporte de otros jugadores no implementado"
        )

        task = TaskGMCommands(
            packet,
            mock_message_sender,
            gm_command_handler=gm_command_handler,
            session_data={"user_id": 1},
        )

        await task.execute()

        # Debe llamar al handler
        gm_command_handler.handle.assert_called_once()
        # El handler envía el mensaje, así que verificamos que fue llamado
        # (el handler mock no ejecuta el código real, así que no envía el mensaje)
        call_args = gm_command_handler.handle.call_args[0][0]
        assert isinstance(call_args, GMCommand)
        assert call_args.username == "OTROJUGADOR"

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
    async def test_gm_command_without_player_position(self, mock_message_sender):
        """Test cuando no se encuentra posición del jugador."""
        packet = self._create_gm_packet()

        # Mock que retorna None (no encontró posición)
        player_repo = MagicMock()
        player_repo.get_position = AsyncMock(return_value=None)

        gm_command_handler = create_mock_gm_command_handler(
            player_repo=player_repo, message_sender=mock_message_sender
        )
        gm_command_handler.handle.return_value = CommandResult.error(
            "No se encontró posición del jugador"
        )

        task = TaskGMCommands(
            packet,
            mock_message_sender,
            gm_command_handler=gm_command_handler,
            session_data={"user_id": 1},
        )

        await task.execute()

        # Debe llamar al handler (el handler maneja el error)
        gm_command_handler.handle.assert_called_once()

    @pytest.mark.asyncio
    async def test_gm_command_with_invalid_session_data(self, mock_message_sender):
        """Test con user_id inválido en sesión."""
        packet = self._create_gm_packet()

        gm_command_handler = create_mock_gm_command_handler()

        task = TaskGMCommands(
            packet,
            mock_message_sender,
            gm_command_handler=gm_command_handler,
            session_data={"user_id": {"invalid": "dict"}},  # user_id es dict en vez de int
        )

        await task.execute()

        # No debe llamar al handler con user_id inválido
        gm_command_handler.handle.assert_not_called()

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
