"""Tests básicos para TaskWorkLeftClick (sistema de trabajo con click)."""

import struct
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.commands.base import CommandResult
from src.commands.work_left_click_command import WorkLeftClickCommand
from src.network.packet_id import ClientPacketID
from src.tasks.work.task_work_left_click import TaskWorkLeftClick


@pytest.fixture
def mock_message_sender():
    """Mock de message_sender con métodos async."""
    sender = MagicMock()
    sender.console.send_console_msg = AsyncMock()
    sender.console.send_error_msg = AsyncMock()
    sender.send_change_inventory_slot = AsyncMock()
    return sender


def create_mock_work_left_click_handler(
    player_repo: MagicMock | None = None,
    inventory_repo: MagicMock | None = None,
    map_resources: MagicMock | None = None,
    message_sender: MagicMock | None = None,
) -> MagicMock:
    """Crea un mock de WorkLeftClickCommandHandler con las dependencias especificadas."""
    handler = MagicMock()
    handler.player_repo = player_repo or MagicMock()
    handler.inventory_repo = inventory_repo or MagicMock()
    handler.map_resources = map_resources or MagicMock()
    handler.message_sender = message_sender or MagicMock()
    handler.handle = AsyncMock()
    return handler


class TestTaskWorkLeftClick:
    """Tests para TaskWorkLeftClick."""

    def _create_work_packet(self, x: int, y: int, skill: int) -> bytes:
        """Crea un packet WORK_LEFT_CLICK."""
        return struct.pack("BBBB", ClientPacketID.WORK_LEFT_CLICK, x, y, skill)

    @pytest.mark.asyncio
    async def test_work_without_session(self, mock_message_sender):
        """Test sin sesión activa debe mostrar error."""
        packet = self._create_work_packet(x=50, y=50, skill=9)  # SKILL_TALAR

        work_left_click_handler = create_mock_work_left_click_handler(
            message_sender=mock_message_sender
        )

        task = TaskWorkLeftClick(
            packet,
            mock_message_sender,
            work_left_click_handler=work_left_click_handler,
            player_repo=AsyncMock(),
            session_data={},  # Sin user_id
        )
        await task.execute()

        # Debe enviar mensaje de error
        mock_message_sender.console.send_error_msg.assert_called_once()
        call_args = mock_message_sender.console.send_error_msg.call_args[0][0]
        assert "sesión" in call_args.lower()
        # No debe llamar al handler
        work_left_click_handler.handle.assert_not_called()

    @pytest.mark.asyncio
    async def test_work_without_player_repo(self, mock_message_sender):
        """Test sin player_repo debe mostrar error."""
        packet = self._create_work_packet(x=50, y=50, skill=9)

        work_left_click_handler = create_mock_work_left_click_handler(
            message_sender=mock_message_sender
        )

        task = TaskWorkLeftClick(
            packet,
            mock_message_sender,
            work_left_click_handler=work_left_click_handler,
            player_repo=None,  # Sin repo
            session_data={"user_id": 1},
        )
        await task.execute()

        # Debe enviar mensaje de error
        mock_message_sender.console.send_error_msg.assert_called_once()
        # No debe llamar al handler
        work_left_click_handler.handle.assert_not_called()

    @pytest.mark.asyncio
    async def test_work_invalid_packet_size(self, mock_message_sender):
        """Test con packet muy corto debe retornar sin hacer nada."""
        # Packet de solo 2 bytes (inválido)
        packet = struct.pack("BB", ClientPacketID.WORK_LEFT_CLICK, 50)

        work_left_click_handler = create_mock_work_left_click_handler(
            message_sender=mock_message_sender
        )

        task = TaskWorkLeftClick(
            packet,
            mock_message_sender,
            work_left_click_handler=work_left_click_handler,
            player_repo=AsyncMock(),
            session_data={"user_id": 1},
        )
        await task.execute()

        # No debe llamar al handler porque el packet es inválido
        work_left_click_handler.handle.assert_not_called()

    @pytest.mark.asyncio
    async def test_work_packet_parsing(self, mock_message_sender):
        """Test que verifica que el packet se parsea correctamente."""
        packet = self._create_work_packet(x=50, y=60, skill=9)

        work_left_click_handler = create_mock_work_left_click_handler(
            message_sender=mock_message_sender
        )

        player_repo = AsyncMock()
        player_repo.get_position.return_value = None  # Player sin posición

        task = TaskWorkLeftClick(
            packet,
            mock_message_sender,
            work_left_click_handler=work_left_click_handler,
            player_repo=player_repo,
            session_data={"user_id": 1},
        )
        await task.execute()

        # Debe haber intentado obtener la posición del jugador
        player_repo.get_position.assert_called_once_with(1)
        # No debe llamar al handler si no hay posición
        work_left_click_handler.handle.assert_not_called()

    @pytest.mark.asyncio
    async def test_work_different_skills(self):
        """Test que diferentes skills crean packets diferentes."""
        packet_talar = self._create_work_packet(x=50, y=50, skill=9)
        packet_pesca = self._create_work_packet(x=50, y=50, skill=12)
        packet_minar = self._create_work_packet(x=50, y=50, skill=13)

        # Verificar que los bytes son diferentes
        assert packet_talar[3] == 9
        assert packet_pesca[3] == 12
        assert packet_minar[3] == 13

    @pytest.mark.asyncio
    async def test_work_coordinates_parsing(self):
        """Test que las coordenadas se parsean correctamente."""
        x, y = 45, 67
        packet = self._create_work_packet(x=x, y=y, skill=9)

        # Verificar que los bytes están correctos
        assert packet[1] == x
        assert packet[2] == y

    @pytest.mark.asyncio
    async def test_work_task_creation(self, mock_message_sender):
        """Test que la task se puede crear con todas las dependencias."""
        packet = self._create_work_packet(x=50, y=50, skill=9)

        work_left_click_handler = create_mock_work_left_click_handler()

        task = TaskWorkLeftClick(
            packet,
            mock_message_sender,
            work_left_click_handler=work_left_click_handler,
            player_repo=AsyncMock(),
            session_data={"user_id": 1},
        )

        # Verificar que la task se creó correctamente
        assert task is not None
        assert task.data == packet
        assert task.message_sender == mock_message_sender

    @pytest.mark.asyncio
    async def test_work_success(self, mock_message_sender):
        """Test trabajar exitosamente."""
        packet = self._create_work_packet(x=51, y=50, skill=9)

        work_left_click_handler = create_mock_work_left_click_handler(
            message_sender=mock_message_sender
        )
        work_left_click_handler.handle.return_value = CommandResult.ok(
            data={
                "resource_name": "Leña",
                "item_id": 58,
                "quantity": 5,
                "slot": 5,
                "skill_name": "Talar",
                "exp_gained": 10,
                "leveled_up": False,
            }
        )

        player_repo = AsyncMock()
        player_repo.get_position.return_value = {"x": 50, "y": 50, "map": 1}

        task = TaskWorkLeftClick(
            packet,
            mock_message_sender,
            work_left_click_handler=work_left_click_handler,
            player_repo=player_repo,
            session_data={"user_id": 1},
        )
        await task.execute()

        # Debe llamar al handler con el comando correcto
        work_left_click_handler.handle.assert_called_once()
        call_args = work_left_click_handler.handle.call_args[0][0]
        assert isinstance(call_args, WorkLeftClickCommand)
        assert call_args.user_id == 1
        assert call_args.map_id == 1
        assert call_args.target_x == 51
        assert call_args.target_y == 50
        assert call_args.skill_type == 9

    @pytest.mark.asyncio
    async def test_work_failure(self, mock_message_sender):
        """Test cuando falla el trabajo."""
        packet = self._create_work_packet(x=51, y=50, skill=9)

        work_left_click_handler = create_mock_work_left_click_handler(
            message_sender=mock_message_sender
        )
        work_left_click_handler.handle.return_value = CommandResult.error(
            "No hay nada para trabajar en esa posición"
        )

        player_repo = AsyncMock()
        player_repo.get_position.return_value = {"x": 50, "y": 50, "map": 1}

        task = TaskWorkLeftClick(
            packet,
            mock_message_sender,
            work_left_click_handler=work_left_click_handler,
            player_repo=player_repo,
            session_data={"user_id": 1},
        )
        await task.execute()

        # Debe llamar al handler
        work_left_click_handler.handle.assert_called_once()

    @pytest.mark.asyncio
    async def test_work_without_handler(self, mock_message_sender):
        """Test sin handler debe mostrar error."""
        packet = self._create_work_packet(x=51, y=50, skill=9)

        player_repo = AsyncMock()
        player_repo.get_position.return_value = {"x": 50, "y": 50, "map": 1}

        task = TaskWorkLeftClick(
            packet,
            mock_message_sender,
            work_left_click_handler=None,
            player_repo=player_repo,
            session_data={"user_id": 1},
        )
        await task.execute()

        # Debe enviar mensaje de error
        mock_message_sender.console.send_error_msg.assert_called_once()

    @pytest.mark.asyncio
    async def test_extract_work_data(self, mock_message_sender):
        """Test que _extract_work_data parsea correctamente."""
        packet = self._create_work_packet(x=45, y=67, skill=12)

        task = TaskWorkLeftClick(
            packet,
            mock_message_sender,
            work_left_click_handler=create_mock_work_left_click_handler(),
            player_repo=AsyncMock(),
            session_data={"user_id": 1},
        )

        target_x, target_y, skill_type = task._extract_work_data()

        assert target_x == 45
        assert target_y == 67
        assert skill_type == 12

    @pytest.mark.asyncio
    async def test_extract_work_data_invalid_packet(self, mock_message_sender):
        """Test que _extract_work_data lanza IndexError con packet inválido."""
        packet = struct.pack("BB", ClientPacketID.WORK_LEFT_CLICK, 50)  # Muy corto

        task = TaskWorkLeftClick(
            packet,
            mock_message_sender,
            work_left_click_handler=create_mock_work_left_click_handler(),
            player_repo=AsyncMock(),
            session_data={"user_id": 1},
        )

        with pytest.raises(IndexError):
            task._extract_work_data()
