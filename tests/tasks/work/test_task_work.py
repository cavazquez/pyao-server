"""Tests para TaskWork (sistema de trabajo con tecla U)."""

import struct
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.commands.base import CommandResult
from src.commands.work_command import WorkCommand
from src.network.packet_id import ClientPacketID
from src.tasks.work.task_work import (
    HEADING_EAST,
    HEADING_NORTH,
    HEADING_SOUTH,
    HEADING_WEST,
    TaskWork,
)


@pytest.fixture
def mock_message_sender():
    """Mock de message_sender con métodos async."""
    sender = MagicMock()
    sender.console.send_console_msg = AsyncMock()
    sender.console.send_error_msg = AsyncMock()
    sender.send_change_inventory_slot = AsyncMock()
    return sender


@pytest.fixture
def mock_player_repo():
    """Mock de PlayerRepository."""
    repo = AsyncMock()
    repo.get_position.return_value = {"x": 50, "y": 50, "map": 1, "heading": HEADING_NORTH}
    return repo


def create_mock_work_handler(
    player_repo: MagicMock | None = None,
    inventory_repo: MagicMock | None = None,
    map_resources: MagicMock | None = None,
    message_sender: MagicMock | None = None,
) -> MagicMock:
    """Crea un mock de WorkCommandHandler con las dependencias especificadas."""
    handler = MagicMock()
    handler.player_repo = player_repo or MagicMock()
    handler.inventory_repo = inventory_repo or MagicMock()
    handler.map_resources = map_resources or MagicMock()
    handler.message_sender = message_sender or MagicMock()
    handler.handle = AsyncMock()
    return handler


class TestTaskWork:
    """Tests para TaskWork."""

    def _create_work_packet(self) -> bytes:
        """Crea un packet WORK (tecla U)."""
        return struct.pack("B", ClientPacketID.WORK)

    @pytest.mark.asyncio
    async def test_work_without_session(self, mock_message_sender):
        """Test sin sesión activa debe mostrar error."""
        packet = self._create_work_packet()

        work_handler = create_mock_work_handler(message_sender=mock_message_sender)

        task = TaskWork(
            packet,
            mock_message_sender,
            work_handler=work_handler,
            player_repo=AsyncMock(),
            session_data={},  # Sin user_id
        )
        await task.execute()

        # Debe enviar mensaje de error
        mock_message_sender.console.send_error_msg.assert_called_once()
        call_args = mock_message_sender.console.send_error_msg.call_args[0][0]
        assert "sesión" in call_args.lower()
        # No debe llamar al handler
        work_handler.handle.assert_not_called()

    @pytest.mark.asyncio
    async def test_work_without_player_repo(self, mock_message_sender):
        """Test sin player_repo debe mostrar error."""
        packet = self._create_work_packet()

        work_handler = create_mock_work_handler(message_sender=mock_message_sender)

        task = TaskWork(
            packet,
            mock_message_sender,
            work_handler=work_handler,
            player_repo=None,  # Sin repo
            session_data={"user_id": 1},
        )
        await task.execute()

        # Debe enviar mensaje de error
        mock_message_sender.console.send_error_msg.assert_called_once()
        # No debe llamar al handler
        work_handler.handle.assert_not_called()

    @pytest.mark.asyncio
    async def test_work_without_position(self, mock_message_sender, mock_player_repo):
        """Test cuando el jugador no tiene posición."""
        packet = self._create_work_packet()

        work_handler = create_mock_work_handler(message_sender=mock_message_sender)

        mock_player_repo.get_position.return_value = None  # Sin posición

        task = TaskWork(
            packet,
            mock_message_sender,
            work_handler=work_handler,
            player_repo=mock_player_repo,
            session_data={"user_id": 1},
        )
        await task.execute()

        # Debe haber intentado obtener la posición
        mock_player_repo.get_position.assert_called_once_with(1)
        # No debe llamar al handler si no hay posición
        work_handler.handle.assert_not_called()

    @pytest.mark.asyncio
    async def test_work_success(self, mock_message_sender, mock_player_repo):
        """Test trabajar exitosamente."""
        packet = self._create_work_packet()

        work_handler = create_mock_work_handler(message_sender=mock_message_sender)
        work_handler.handle.return_value = CommandResult.ok(
            data={"resource_name": "Leña", "item_id": 1, "quantity": 5}
        )

        task = TaskWork(
            packet,
            mock_message_sender,
            work_handler=work_handler,
            player_repo=mock_player_repo,
            session_data={"user_id": 1},
        )
        await task.execute()

        # Debe llamar al handler con el comando correcto
        work_handler.handle.assert_called_once()
        call_args = work_handler.handle.call_args[0][0]
        assert isinstance(call_args, WorkCommand)
        assert call_args.user_id == 1
        assert call_args.map_id == 1
        assert call_args.target_x == 50
        assert call_args.target_y == 49  # Norte: y - 1

    @pytest.mark.asyncio
    async def test_work_failure(self, mock_message_sender, mock_player_repo):
        """Test cuando falla el trabajo."""
        packet = self._create_work_packet()

        work_handler = create_mock_work_handler(message_sender=mock_message_sender)
        work_handler.handle.return_value = CommandResult.error(
            "No hay nada para trabajar en esa dirección"
        )

        task = TaskWork(
            packet,
            mock_message_sender,
            work_handler=work_handler,
            player_repo=mock_player_repo,
            session_data={"user_id": 1},
        )
        await task.execute()

        # Debe llamar al handler
        work_handler.handle.assert_called_once()

    @pytest.mark.asyncio
    async def test_work_without_handler(self, mock_message_sender, mock_player_repo):
        """Test sin handler debe mostrar error."""
        packet = self._create_work_packet()

        task = TaskWork(
            packet,
            mock_message_sender,
            work_handler=None,
            player_repo=mock_player_repo,
            session_data={"user_id": 1},
        )
        await task.execute()

        # Debe enviar mensaje de error
        mock_message_sender.console.send_error_msg.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_target_position_north(self):
        """Test cálculo de posición objetivo mirando al norte."""
        target_x, target_y = TaskWork._get_target_position(50, 50, HEADING_NORTH)
        assert target_x == 50
        assert target_y == 49  # y - 1

    @pytest.mark.asyncio
    async def test_get_target_position_east(self):
        """Test cálculo de posición objetivo mirando al este."""
        target_x, target_y = TaskWork._get_target_position(50, 50, HEADING_EAST)
        assert target_x == 51  # x + 1
        assert target_y == 50

    @pytest.mark.asyncio
    async def test_get_target_position_south(self):
        """Test cálculo de posición objetivo mirando al sur."""
        target_x, target_y = TaskWork._get_target_position(50, 50, HEADING_SOUTH)
        assert target_x == 50
        assert target_y == 51  # y + 1

    @pytest.mark.asyncio
    async def test_get_target_position_west(self):
        """Test cálculo de posición objetivo mirando al oeste."""
        target_x, target_y = TaskWork._get_target_position(50, 50, HEADING_WEST)
        assert target_x == 49  # x - 1
        assert target_y == 50

    @pytest.mark.asyncio
    async def test_work_task_creation(self, mock_message_sender):
        """Test que la task se puede crear con todas las dependencias."""
        packet = self._create_work_packet()

        work_handler = create_mock_work_handler()

        task = TaskWork(
            packet,
            mock_message_sender,
            work_handler=work_handler,
            player_repo=AsyncMock(),
            session_data={"user_id": 1},
        )

        # Verificar que la task se creó correctamente
        assert task is not None
        assert task.data == packet
        assert task.message_sender == mock_message_sender
