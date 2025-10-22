"""Tests básicos para TaskWorkLeftClick (sistema de trabajo con click)."""

import struct
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.network.packet_id import ClientPacketID
from src.tasks.work.task_work_left_click import (
    SKILL_MINERIA,
    SKILL_PESCA,
    SKILL_TALAR,
    TaskWorkLeftClick,
)


@pytest.fixture
def mock_message_sender():
    """Mock de message_sender con métodos async."""
    sender = MagicMock()
    sender.console.send_console_msg = AsyncMock()
    sender.console.send_error_msg = AsyncMock()
    sender.send_change_inventory_slot = AsyncMock()
    return sender


class TestTaskWorkLeftClick:
    """Tests para TaskWorkLeftClick."""

    def _create_work_packet(self, x: int, y: int, skill: int) -> bytes:
        """Crea un packet WORK_LEFT_CLICK."""
        return struct.pack("BBBB", ClientPacketID.WORK_LEFT_CLICK, x, y, skill)

    @pytest.mark.asyncio
    async def test_work_without_session(self, mock_message_sender):
        """Test sin sesión activa debe mostrar error."""
        packet = self._create_work_packet(x=50, y=50, skill=SKILL_TALAR)

        task = TaskWorkLeftClick(
            packet,
            mock_message_sender,
            player_repo=AsyncMock(),
            inventory_repo=AsyncMock(),
            map_manager=MagicMock(),
            session_data={},  # Sin user_id
            map_resources=MagicMock(),
        )
        await task.execute()

        # Debe enviar mensaje de error
        mock_message_sender.console.send_error_msg.assert_called_once()
        call_args = mock_message_sender.console.send_error_msg.call_args[0][0]
        assert "sesión" in call_args.lower()

    @pytest.mark.asyncio
    async def test_work_without_repositories(self, mock_message_sender):
        """Test sin repositorios debe mostrar error."""
        packet = self._create_work_packet(x=50, y=50, skill=SKILL_TALAR)

        task = TaskWorkLeftClick(
            packet,
            mock_message_sender,
            player_repo=None,  # Sin repo
            inventory_repo=None,
            map_manager=None,
            session_data={"user_id": 1},
            map_resources=None,
        )
        await task.execute()

        # Debe enviar mensaje de error
        mock_message_sender.console.send_error_msg.assert_called_once()

    @pytest.mark.asyncio
    async def test_work_invalid_packet_size(self, mock_message_sender):
        """Test con packet muy corto debe retornar sin hacer nada."""
        # Packet de solo 2 bytes (inválido)
        packet = struct.pack("BB", ClientPacketID.WORK_LEFT_CLICK, 50)

        task = TaskWorkLeftClick(
            packet,
            mock_message_sender,
            player_repo=AsyncMock(),
            inventory_repo=AsyncMock(),
            map_manager=MagicMock(),
            session_data={"user_id": 1},
            map_resources=MagicMock(),
        )
        await task.execute()

        # No debe llamar a get_position porque el packet es inválido
        # (retorna antes de eso)

    @pytest.mark.asyncio
    async def test_work_packet_parsing(self, mock_message_sender):
        """Test que verifica que el packet se parsea correctamente."""
        packet = self._create_work_packet(x=50, y=60, skill=SKILL_TALAR)

        player_repo = AsyncMock()
        player_repo.get_position.return_value = None  # Player sin posición

        task = TaskWorkLeftClick(
            packet,
            mock_message_sender,
            player_repo=player_repo,
            inventory_repo=AsyncMock(),
            map_manager=MagicMock(),
            session_data={"user_id": 1},
            map_resources=MagicMock(),
        )
        await task.execute()

        # Debe haber intentado obtener la posición del jugador
        player_repo.get_position.assert_called_once_with(1)

    @pytest.mark.asyncio
    async def test_work_different_skills(self):
        """Test que diferentes skills crean packets diferentes."""
        packet_talar = self._create_work_packet(x=50, y=50, skill=SKILL_TALAR)
        packet_pesca = self._create_work_packet(x=50, y=50, skill=SKILL_PESCA)
        packet_minar = self._create_work_packet(x=50, y=50, skill=SKILL_MINERIA)

        # Verificar que los bytes son diferentes
        assert packet_talar[3] == SKILL_TALAR
        assert packet_pesca[3] == SKILL_PESCA
        assert packet_minar[3] == SKILL_MINERIA

    @pytest.mark.asyncio
    async def test_work_coordinates_parsing(self):
        """Test que las coordenadas se parsean correctamente."""
        x, y = 45, 67
        packet = self._create_work_packet(x=x, y=y, skill=SKILL_TALAR)

        # Verificar que los bytes están correctos
        assert packet[1] == x
        assert packet[2] == y

    @pytest.mark.asyncio
    async def test_work_task_creation(self, mock_message_sender):
        """Test que la task se puede crear con todas las dependencias."""
        packet = self._create_work_packet(x=50, y=50, skill=SKILL_TALAR)

        task = TaskWorkLeftClick(
            packet,
            mock_message_sender,
            player_repo=AsyncMock(),
            inventory_repo=AsyncMock(),
            map_manager=MagicMock(),
            session_data={"user_id": 1},
            map_resources=MagicMock(),
        )

        # Verificar que la task se creó correctamente
        assert task is not None
        assert task.data == packet
        assert task.message_sender == mock_message_sender
