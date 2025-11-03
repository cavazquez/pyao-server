"""Tests para TaskWork (sistema de trabajo con tecla U)."""

import struct
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.constants.items import ResourceItemID, ToolID
from src.network.packet_id import ClientPacketID
from src.tasks.work.task_work import (
    HEADING_EAST,
    HEADING_NORTH,
    HEADING_SOUTH,
    HEADING_WEST,
    TaskWork,
)
from src.utils.inventory_slot import InventorySlot


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


@pytest.fixture
def mock_inventory_repo():
    """Mock de InventoryRepository."""
    repo = AsyncMock()
    repo.get_inventory_slots.return_value = {}
    repo.add_item = AsyncMock()
    return repo


@pytest.fixture
def mock_map_resources():
    """Mock de MapResourcesService."""
    service = MagicMock()
    service.has_tree.return_value = False
    service.has_mine.return_value = False
    service.has_water.return_value = False
    return service


class TestTaskWork:
    """Tests para TaskWork."""

    def _create_work_packet(self) -> bytes:
        """Crea un packet WORK (tecla U)."""
        return struct.pack("B", ClientPacketID.WORK)

    @pytest.mark.asyncio
    async def test_work_without_session(self, mock_message_sender):
        """Test sin sesión activa debe mostrar error."""
        packet = self._create_work_packet()

        task = TaskWork(
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
        packet = self._create_work_packet()

        task = TaskWork(
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
    async def test_work_without_position(
        self, mock_message_sender, mock_inventory_repo, mock_map_resources
    ):
        """Test cuando el jugador no tiene posición."""
        packet = self._create_work_packet()

        player_repo = AsyncMock()
        player_repo.get_position.return_value = None  # Sin posición

        task = TaskWork(
            packet,
            mock_message_sender,
            player_repo=player_repo,
            inventory_repo=mock_inventory_repo,
            map_manager=MagicMock(),
            session_data={"user_id": 1},
            map_resources=mock_map_resources,
        )
        await task.execute()

        # Debe haber intentado obtener la posición
        player_repo.get_position.assert_called_once_with(1)

    @pytest.mark.asyncio
    async def test_work_without_tool(
        self, mock_message_sender, mock_player_repo, mock_inventory_repo, mock_map_resources
    ):
        """Test trabajar sin herramienta."""
        packet = self._create_work_packet()

        # Inventario vacío (sin herramientas)
        mock_inventory_repo.get_inventory_slots.return_value = {}

        task = TaskWork(
            packet,
            mock_message_sender,
            player_repo=mock_player_repo,
            inventory_repo=mock_inventory_repo,
            map_manager=MagicMock(),
            session_data={"user_id": 1},
            map_resources=mock_map_resources,
        )
        await task.execute()

        # Debe enviar mensaje indicando que no hay nada o que necesita herramienta
        # El mensaje puede ser "No hay nada para trabajar" o "Necesitas una herramienta"
        mock_message_sender.console.send_console_msg.assert_called()

    @pytest.mark.asyncio
    async def test_work_chop_tree_with_axe(
        self, mock_message_sender, mock_player_repo, mock_inventory_repo, mock_map_resources
    ):
        """Test talar árbol con hacha."""
        packet = self._create_work_packet()

        # Jugador mirando al norte (y-1)
        mock_player_repo.get_position.return_value = {
            "x": 50,
            "y": 50,
            "map": 1,
            "heading": HEADING_NORTH,
        }

        # Inventario con hacha
        mock_inventory_repo.get_inventory_slots.return_value = {
            1: InventorySlot(item_id=ToolID.HACHA_LENADOR, quantity=1)
        }

        # Hay un árbol al norte (50, 49)
        mock_map_resources.has_tree.return_value = True

        task = TaskWork(
            packet,
            mock_message_sender,
            player_repo=mock_player_repo,
            inventory_repo=mock_inventory_repo,
            map_manager=MagicMock(),
            session_data={"user_id": 1},
            map_resources=mock_map_resources,
        )
        await task.execute()

        # Debe verificar árbol en la posición correcta
        mock_map_resources.has_tree.assert_called_once_with(1, 50, 49)

        # Debe agregar leña al inventario
        mock_inventory_repo.add_item.assert_called_once_with(
            1, item_id=ResourceItemID.LENA, quantity=5
        )

        # Debe enviar mensaje de éxito
        mock_message_sender.console.send_console_msg.assert_called()
        call_args = mock_message_sender.console.send_console_msg.call_args[0][0]
        assert "leña" in call_args.lower()

    @pytest.mark.asyncio
    async def test_work_mine_with_pickaxe(
        self, mock_message_sender, mock_player_repo, mock_inventory_repo, mock_map_resources
    ):
        """Test minar con pico."""
        packet = self._create_work_packet()

        # Jugador mirando al este (x+1)
        mock_player_repo.get_position.return_value = {
            "x": 50,
            "y": 50,
            "map": 1,
            "heading": HEADING_EAST,
        }

        # Inventario con pico
        mock_inventory_repo.get_inventory_slots.return_value = {
            1: InventorySlot(item_id=ToolID.PIQUETE_MINERO, quantity=1)
        }

        # Hay una mina al este (51, 50)
        mock_map_resources.has_mine.return_value = True

        task = TaskWork(
            packet,
            mock_message_sender,
            player_repo=mock_player_repo,
            inventory_repo=mock_inventory_repo,
            map_manager=MagicMock(),
            session_data={"user_id": 1},
            map_resources=mock_map_resources,
        )
        await task.execute()

        # Debe verificar mina en la posición correcta
        mock_map_resources.has_mine.assert_called_once_with(1, 51, 50)

        # Debe agregar mineral al inventario
        mock_inventory_repo.add_item.assert_called_once_with(
            1, item_id=ResourceItemID.MINERAL_HIERRO, quantity=3
        )

        # Debe enviar mensaje de éxito
        mock_message_sender.console.send_console_msg.assert_called()
        call_args = mock_message_sender.console.send_console_msg.call_args[0][0]
        assert "mineral" in call_args.lower() or "hierro" in call_args.lower()

    @pytest.mark.asyncio
    async def test_work_fish_with_rod(
        self, mock_message_sender, mock_player_repo, mock_inventory_repo, mock_map_resources
    ):
        """Test pescar con caña."""
        packet = self._create_work_packet()

        # Jugador mirando al sur (y+1)
        mock_player_repo.get_position.return_value = {
            "x": 50,
            "y": 50,
            "map": 1,
            "heading": HEADING_SOUTH,
        }

        # Inventario con caña de pescar
        mock_inventory_repo.get_inventory_slots.return_value = {
            1: InventorySlot(item_id=ToolID.CANA_PESCAR, quantity=1)
        }

        # Hay agua al sur (50, 51)
        mock_map_resources.has_water.return_value = True

        task = TaskWork(
            packet,
            mock_message_sender,
            player_repo=mock_player_repo,
            inventory_repo=mock_inventory_repo,
            map_manager=MagicMock(),
            session_data={"user_id": 1},
            map_resources=mock_map_resources,
        )
        await task.execute()

        # Debe verificar agua en la posición correcta
        mock_map_resources.has_water.assert_called_once_with(1, 50, 51)

        # Debe agregar pescado al inventario
        mock_inventory_repo.add_item.assert_called_once_with(
            1, item_id=ResourceItemID.PESCADO, quantity=2
        )

        # Debe enviar mensaje de éxito
        mock_message_sender.console.send_console_msg.assert_called()
        call_args = mock_message_sender.console.send_console_msg.call_args[0][0]
        assert "pescado" in call_args.lower()

    @pytest.mark.asyncio
    async def test_work_no_resource_at_target(
        self, mock_message_sender, mock_player_repo, mock_inventory_repo, mock_map_resources
    ):
        """Test trabajar cuando no hay recurso en la dirección."""
        packet = self._create_work_packet()

        # Inventario con hacha
        mock_inventory_repo.get_inventory_slots.return_value = {
            1: InventorySlot(item_id=ToolID.HACHA_LENADOR, quantity=1)
        }

        # No hay recursos en ninguna dirección
        mock_map_resources.has_tree.return_value = False
        mock_map_resources.has_mine.return_value = False
        mock_map_resources.has_water.return_value = False

        task = TaskWork(
            packet,
            mock_message_sender,
            player_repo=mock_player_repo,
            inventory_repo=mock_inventory_repo,
            map_manager=MagicMock(),
            session_data={"user_id": 1},
            map_resources=mock_map_resources,
        )
        await task.execute()

        # Debe enviar mensaje indicando que no hay nada
        mock_message_sender.console.send_console_msg.assert_called()
        call_args = mock_message_sender.console.send_console_msg.call_args[0][0]
        assert "nada" in call_args.lower() or "no hay" in call_args.lower()

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

        task = TaskWork(
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
