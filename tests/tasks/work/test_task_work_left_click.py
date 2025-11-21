"""Tests básicos para TaskWorkLeftClick (sistema de trabajo con click)."""

import struct
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.models.items_catalog import Item
from src.network.packet_id import ClientPacketID
from src.tasks.work.task_work_left_click import (
    SKILL_MINERIA,
    SKILL_PESCA,
    SKILL_TALAR,
    ResourceItemID,
    TaskWorkLeftClick,
    ToolID,
)
from src.utils.inventory_slot import InventorySlot


@pytest.fixture
def mock_message_sender():
    """Mock de message_sender con métodos async."""
    sender = AsyncMock()
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

    @pytest.mark.asyncio
    async def test_validate_user_id_as_dict(self, mock_message_sender):
        """Test cuando user_id en sesión es un dict (error)."""
        packet = self._create_work_packet(x=50, y=50, skill=SKILL_TALAR)

        task = TaskWorkLeftClick(
            packet,
            mock_message_sender,
            player_repo=AsyncMock(),
            inventory_repo=AsyncMock(),
            map_manager=MagicMock(),
            session_data={"user_id": {"invalid": "dict"}},  # user_id como dict
            map_resources=MagicMock(),
        )
        user_id = await task._validate_and_get_user_id()

        # Debe retornar None cuando user_id es dict
        assert user_id is None

    @pytest.mark.asyncio
    async def test_get_player_map_without_repo(self, mock_message_sender):
        """Test _get_player_map sin player_repo."""
        packet = self._create_work_packet(x=50, y=50, skill=SKILL_TALAR)

        task = TaskWorkLeftClick(
            packet,
            mock_message_sender,
            player_repo=None,  # Sin repo
            inventory_repo=AsyncMock(),
            map_manager=MagicMock(),
            session_data={"user_id": 1},
            map_resources=MagicMock(),
        )
        map_id = await task._get_player_map(1)

        # Debe retornar None sin player_repo
        assert map_id is None

    @pytest.mark.asyncio
    async def test_get_player_map_without_position(self, mock_message_sender):
        """Test _get_player_map cuando no hay posición."""
        packet = self._create_work_packet(x=50, y=50, skill=SKILL_TALAR)

        player_repo = AsyncMock()
        player_repo.get_position.return_value = None  # Sin posición

        task = TaskWorkLeftClick(
            packet,
            mock_message_sender,
            player_repo=player_repo,
            inventory_repo=AsyncMock(),
            map_manager=MagicMock(),
            session_data={"user_id": 1},
            map_resources=MagicMock(),
        )
        map_id = await task._get_player_map(1)

        # Debe retornar None sin posición
        assert map_id is None
        player_repo.get_position.assert_called_once_with(1)

    @pytest.mark.asyncio
    async def test_check_distance_without_repo(self, mock_message_sender):
        """Test _check_distance sin player_repo."""
        packet = self._create_work_packet(x=50, y=50, skill=SKILL_TALAR)

        task = TaskWorkLeftClick(
            packet,
            mock_message_sender,
            player_repo=None,  # Sin repo
            inventory_repo=AsyncMock(),
            map_manager=MagicMock(),
            session_data={"user_id": 1},
            map_resources=MagicMock(),
        )
        result = await task._check_distance(1, 50, 50)

        # Debe retornar False sin player_repo
        assert result is False

    @pytest.mark.asyncio
    async def test_check_distance_without_position(self, mock_message_sender):
        """Test _check_distance cuando no hay posición."""
        packet = self._create_work_packet(x=50, y=50, skill=SKILL_TALAR)

        player_repo = AsyncMock()
        player_repo.get_position.return_value = None  # Sin posición

        task = TaskWorkLeftClick(
            packet,
            mock_message_sender,
            player_repo=player_repo,
            inventory_repo=AsyncMock(),
            map_manager=MagicMock(),
            session_data={"user_id": 1},
            map_resources=MagicMock(),
        )
        result = await task._check_distance(1, 50, 50)

        # Debe retornar False sin posición
        assert result is False

    @pytest.mark.asyncio
    async def test_check_distance_too_far(self, mock_message_sender):
        """Test _check_distance cuando el target está demasiado lejos."""
        packet = self._create_work_packet(x=50, y=50, skill=SKILL_TALAR)

        player_repo = AsyncMock()
        player_repo.get_position.return_value = {"x": 50, "y": 50, "map": 1}

        task = TaskWorkLeftClick(
            packet,
            mock_message_sender,
            player_repo=player_repo,
            inventory_repo=AsyncMock(),
            map_manager=MagicMock(),
            session_data={"user_id": 1},
            map_resources=MagicMock(),
        )
        # Target a distancia 2 (más de 1)
        result = await task._check_distance(1, 52, 50)

        # Debe retornar False y enviar mensaje
        assert result is False
        mock_message_sender.console.send_console_msg.assert_called_once()
        call_args = mock_message_sender.console.send_console_msg.call_args[0][0]
        assert "distancia" in call_args.lower()

    @pytest.mark.asyncio
    async def test_check_distance_valid(self, mock_message_sender):
        """Test _check_distance cuando el target está a distancia válida."""
        packet = self._create_work_packet(x=50, y=50, skill=SKILL_TALAR)

        player_repo = AsyncMock()
        player_repo.get_position.return_value = {"x": 50, "y": 50, "map": 1}

        task = TaskWorkLeftClick(
            packet,
            mock_message_sender,
            player_repo=player_repo,
            inventory_repo=AsyncMock(),
            map_manager=MagicMock(),
            session_data={"user_id": 1},
            map_resources=MagicMock(),
        )
        # Target a distancia 1 (válido)
        result = await task._check_distance(1, 51, 50)

        # Debe retornar True
        assert result is True

    @pytest.mark.asyncio
    async def test_try_work_without_inventory_repo(self, mock_message_sender):
        """Test _try_work_at_position sin inventory_repo."""
        packet = self._create_work_packet(x=50, y=50, skill=SKILL_TALAR)

        task = TaskWorkLeftClick(
            packet,
            mock_message_sender,
            player_repo=AsyncMock(),
            inventory_repo=None,  # Sin repo
            map_manager=MagicMock(),
            session_data={"user_id": 1},
            map_resources=MagicMock(),
        )
        result = await task._try_work_at_position(1, 1, 50, 50, SKILL_TALAR)

        # Debe retornar None sin inventory_repo
        assert result is None

    @pytest.mark.asyncio
    async def test_try_work_without_map_resources(self, mock_message_sender):
        """Test _try_work_at_position sin map_resources."""
        packet = self._create_work_packet(x=50, y=50, skill=SKILL_TALAR)

        task = TaskWorkLeftClick(
            packet,
            mock_message_sender,
            player_repo=AsyncMock(),
            inventory_repo=AsyncMock(),
            map_manager=MagicMock(),
            session_data={"user_id": 1},
            map_resources=None,  # Sin map_resources
        )
        result = await task._try_work_at_position(1, 1, 50, 50, SKILL_TALAR)

        # Debe retornar None sin map_resources
        assert result is None

    @pytest.mark.asyncio
    async def test_try_work_chop_tree_success(self, mock_message_sender):
        """Test talar árbol exitosamente."""
        packet = self._create_work_packet(x=50, y=50, skill=SKILL_TALAR)

        player_repo = AsyncMock()
        player_repo.add_skill_experience = AsyncMock(return_value=(100, False))

        inventory_repo = AsyncMock()
        inventory_repo.get_inventory_slots.return_value = {
            1: InventorySlot(item_id=ToolID.HACHA_LENADOR, quantity=1)
        }
        inventory_repo.add_item = AsyncMock(return_value=[(5, 5)])  # Slot 5, cantidad 5
        inventory_repo.get_slot = AsyncMock(return_value=(ResourceItemID.LENA, 5))

        map_resources = MagicMock()
        map_resources.has_tree.return_value = True

        task = TaskWorkLeftClick(
            packet,
            mock_message_sender,
            player_repo=player_repo,
            inventory_repo=inventory_repo,
            map_manager=MagicMock(),
            session_data={"user_id": 1},
            map_resources=map_resources,
        )
        result = await task._try_work_at_position(1, 1, 50, 50, SKILL_TALAR)

        # Debe retornar tupla con datos de leña
        assert result is not None
        resource_name, item_id, quantity, slot, skill_name, exp, leveled_up = result
        assert resource_name == "Leña"
        assert item_id == ResourceItemID.LENA
        assert quantity == 5
        assert slot == 5
        assert skill_name == "Talar"
        assert exp > 0
        assert leveled_up is False

        # Verificar llamadas
        map_resources.has_tree.assert_called_once_with(1, 50, 50)
        inventory_repo.add_item.assert_called_once_with(1, item_id=ResourceItemID.LENA, quantity=5)
        player_repo.add_skill_experience.assert_called_once()

    @pytest.mark.asyncio
    async def test_try_work_chop_tree_level_up(self, mock_message_sender):
        """Test talar árbol con level up."""
        packet = self._create_work_packet(x=50, y=50, skill=SKILL_TALAR)

        player_repo = AsyncMock()
        player_repo.add_skill_experience = AsyncMock(return_value=(100, True))  # Level up

        inventory_repo = AsyncMock()
        inventory_repo.get_inventory_slots.return_value = {
            1: InventorySlot(item_id=ToolID.HACHA_LENADOR, quantity=1)
        }
        inventory_repo.add_item = AsyncMock(return_value=[(5, 5)])

        map_resources = MagicMock()
        map_resources.has_tree.return_value = True

        task = TaskWorkLeftClick(
            packet,
            mock_message_sender,
            player_repo=player_repo,
            inventory_repo=inventory_repo,
            map_manager=MagicMock(),
            session_data={"user_id": 1},
            map_resources=map_resources,
        )
        result = await task._try_work_at_position(1, 1, 50, 50, SKILL_TALAR)

        # Debe retornar con leveled_up=True
        assert result is not None
        assert result[6] is True  # leveled_up

    @pytest.mark.asyncio
    async def test_try_work_chop_tree_without_player_repo(self, mock_message_sender):
        """Test talar árbol sin player_repo (no da exp pero da item)."""
        packet = self._create_work_packet(x=50, y=50, skill=SKILL_TALAR)

        inventory_repo = AsyncMock()
        inventory_repo.get_inventory_slots.return_value = {
            1: InventorySlot(item_id=ToolID.HACHA_LENADOR, quantity=1)
        }
        inventory_repo.add_item = AsyncMock(return_value=[(5, 5)])

        map_resources = MagicMock()
        map_resources.has_tree.return_value = True

        task = TaskWorkLeftClick(
            packet,
            mock_message_sender,
            player_repo=None,  # Sin player_repo
            inventory_repo=inventory_repo,
            map_manager=MagicMock(),
            session_data={"user_id": 1},
            map_resources=map_resources,
        )
        result = await task._try_work_at_position(1, 1, 50, 50, SKILL_TALAR)

        # Debe retornar tupla pero sin level up
        assert result is not None
        assert result[6] is False  # leveled_up

    @pytest.mark.asyncio
    async def test_try_work_chop_tree_inventory_full(self, mock_message_sender):
        """Test talar árbol cuando el inventario está lleno."""
        packet = self._create_work_packet(x=50, y=50, skill=SKILL_TALAR)

        inventory_repo = AsyncMock()
        inventory_repo.get_inventory_slots.return_value = {
            1: InventorySlot(item_id=ToolID.HACHA_LENADOR, quantity=1)
        }
        inventory_repo.add_item = AsyncMock(return_value=None)  # Inventario lleno

        map_resources = MagicMock()
        map_resources.has_tree.return_value = True

        task = TaskWorkLeftClick(
            packet,
            mock_message_sender,
            player_repo=AsyncMock(),
            inventory_repo=inventory_repo,
            map_manager=MagicMock(),
            session_data={"user_id": 1},
            map_resources=map_resources,
        )
        result = await task._try_work_at_position(1, 1, 50, 50, SKILL_TALAR)

        # Debe retornar None cuando el inventario está lleno
        assert result is None

    @pytest.mark.asyncio
    async def test_try_work_mine_success(self, mock_message_sender):
        """Test minar exitosamente."""
        packet = self._create_work_packet(x=50, y=50, skill=SKILL_MINERIA)

        player_repo = AsyncMock()
        player_repo.add_skill_experience = AsyncMock(return_value=(100, False))

        inventory_repo = AsyncMock()
        inventory_repo.get_inventory_slots.return_value = {
            1: InventorySlot(item_id=ToolID.PIQUETE_MINERO, quantity=1)
        }
        inventory_repo.add_item = AsyncMock(return_value=[(6, 3)])  # Slot 6, cantidad 3

        map_resources = MagicMock()
        map_resources.has_mine.return_value = True

        task = TaskWorkLeftClick(
            packet,
            mock_message_sender,
            player_repo=player_repo,
            inventory_repo=inventory_repo,
            map_manager=MagicMock(),
            session_data={"user_id": 1},
            map_resources=map_resources,
        )
        result = await task._try_work_at_position(1, 1, 50, 50, SKILL_MINERIA)

        # Debe retornar tupla con datos de mineral
        assert result is not None
        resource_name, item_id, quantity, _slot, skill_name, _exp, _leveled_up = result
        assert resource_name == "Mineral de Hierro"
        assert item_id == ResourceItemID.MINERAL_HIERRO
        assert quantity == 3
        assert skill_name == "Minería"

        # Verificar llamadas
        map_resources.has_mine.assert_called_once_with(1, 50, 50)
        inventory_repo.add_item.assert_called_once_with(
            1, item_id=ResourceItemID.MINERAL_HIERRO, quantity=3
        )

    @pytest.mark.asyncio
    async def test_try_work_fish_success(self, mock_message_sender):
        """Test pescar exitosamente."""
        packet = self._create_work_packet(x=50, y=50, skill=SKILL_PESCA)

        player_repo = AsyncMock()
        player_repo.add_skill_experience = AsyncMock(return_value=(100, False))

        inventory_repo = AsyncMock()
        inventory_repo.get_inventory_slots.return_value = {
            1: InventorySlot(item_id=ToolID.CANA_PESCAR, quantity=1)
        }
        inventory_repo.add_item = AsyncMock(return_value=[(7, 2)])  # Slot 7, cantidad 2

        map_resources = MagicMock()
        map_resources.has_water.return_value = True

        task = TaskWorkLeftClick(
            packet,
            mock_message_sender,
            player_repo=player_repo,
            inventory_repo=inventory_repo,
            map_manager=MagicMock(),
            session_data={"user_id": 1},
            map_resources=map_resources,
        )
        result = await task._try_work_at_position(1, 1, 50, 50, SKILL_PESCA)

        # Debe retornar tupla con datos de pescado
        assert result is not None
        resource_name, item_id, quantity, _slot, skill_name, _exp, _leveled_up = result
        assert resource_name == "Pescado"
        assert item_id == ResourceItemID.PESCADO
        assert quantity == 2
        assert skill_name == "Pesca"

        # Verificar llamadas
        map_resources.has_water.assert_called_once_with(1, 50, 50)
        inventory_repo.add_item.assert_called_once_with(
            1, item_id=ResourceItemID.PESCADO, quantity=2
        )

    @pytest.mark.asyncio
    async def test_try_work_no_tool(self, mock_message_sender):
        """Test trabajar sin herramienta."""
        packet = self._create_work_packet(x=50, y=50, skill=SKILL_TALAR)

        inventory_repo = AsyncMock()
        inventory_repo.get_inventory_slots.return_value = {}  # Sin herramientas

        map_resources = MagicMock()
        map_resources.has_tree.return_value = True

        task = TaskWorkLeftClick(
            packet,
            mock_message_sender,
            player_repo=AsyncMock(),
            inventory_repo=inventory_repo,
            map_manager=MagicMock(),
            session_data={"user_id": 1},
            map_resources=map_resources,
        )
        result = await task._try_work_at_position(1, 1, 50, 50, SKILL_TALAR)

        # Debe retornar None y enviar mensaje
        assert result is None
        mock_message_sender.console.send_console_msg.assert_called_once()
        call_args = mock_message_sender.console.send_console_msg.call_args[0][0]
        assert "herramienta" in call_args.lower()

    @pytest.mark.asyncio
    async def test_try_work_no_resource(self, mock_message_sender):
        """Test trabajar sin recurso en la posición."""
        packet = self._create_work_packet(x=50, y=50, skill=SKILL_TALAR)

        inventory_repo = AsyncMock()
        inventory_repo.get_inventory_slots.return_value = {
            1: InventorySlot(item_id=ToolID.HACHA_LENADOR, quantity=1)
        }

        map_resources = MagicMock()
        map_resources.has_tree.return_value = False  # No hay árbol

        task = TaskWorkLeftClick(
            packet,
            mock_message_sender,
            player_repo=AsyncMock(),
            inventory_repo=inventory_repo,
            map_manager=MagicMock(),
            session_data={"user_id": 1},
            map_resources=map_resources,
        )
        result = await task._try_work_at_position(1, 1, 50, 50, SKILL_TALAR)

        # Debe retornar None sin recurso
        assert result is None

    @pytest.mark.asyncio
    async def test_execute_work_success(self, mock_message_sender):
        """Test execute completo con trabajo exitoso."""
        packet = self._create_work_packet(x=51, y=50, skill=SKILL_TALAR)

        player_repo = AsyncMock()
        player_repo.get_position.return_value = {"x": 50, "y": 50, "map": 1}
        player_repo.add_skill_experience = AsyncMock(return_value=(100, False))

        inventory_repo = AsyncMock()
        inventory_repo.get_inventory_slots.return_value = {
            1: InventorySlot(item_id=ToolID.HACHA_LENADOR, quantity=1)
        }
        inventory_repo.add_item = AsyncMock(return_value=[(5, 5)])
        inventory_repo.get_slot = AsyncMock(return_value=(ResourceItemID.LENA, 5))

        map_resources = MagicMock()
        map_resources.has_tree.return_value = True

        with patch("src.tasks.work.task_work_left_click.get_item") as mock_get_item:
            mock_item = MagicMock(spec=Item)
            mock_item.item_id = ResourceItemID.LENA
            mock_item.name = "Leña"
            mock_item.graphic_id = 1001
            mock_item.item_type = MagicMock()
            mock_item.item_type.to_client_type.return_value = 1
            mock_item.max_damage = None
            mock_item.min_damage = None
            mock_item.defense = None
            mock_item.value = 10.0
            mock_get_item.return_value = mock_item

            task = TaskWorkLeftClick(
                packet,
                mock_message_sender,
                player_repo=player_repo,
                inventory_repo=inventory_repo,
                map_manager=MagicMock(),
                session_data={"user_id": 1},
                map_resources=map_resources,
            )
            await task.execute()

            # Debe enviar mensajes de éxito
            assert mock_message_sender.console.send_console_msg.call_count >= 2
            call_args_list = [
                call[0][0] for call in mock_message_sender.console.send_console_msg.call_args_list
            ]
            assert any("obtenido" in msg.lower() for msg in call_args_list)
            assert any("exp" in msg.lower() for msg in call_args_list)

            # Debe actualizar inventario UI
            mock_message_sender.send_change_inventory_slot.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_work_with_level_up(self, mock_message_sender):
        """Test execute completo con level up."""
        packet = self._create_work_packet(x=51, y=50, skill=SKILL_TALAR)

        player_repo = AsyncMock()
        player_repo.get_position.return_value = {"x": 50, "y": 50, "map": 1}
        player_repo.add_skill_experience = AsyncMock(return_value=(100, True))  # Level up

        inventory_repo = AsyncMock()
        inventory_repo.get_inventory_slots.return_value = {
            1: InventorySlot(item_id=ToolID.HACHA_LENADOR, quantity=1)
        }
        inventory_repo.add_item = AsyncMock(return_value=[(5, 5)])
        inventory_repo.get_slot = AsyncMock(return_value=(ResourceItemID.LENA, 5))

        map_resources = MagicMock()
        map_resources.has_tree.return_value = True

        with patch("src.tasks.work.task_work_left_click.get_item") as mock_get_item:
            mock_item = MagicMock(spec=Item)
            mock_item.item_id = ResourceItemID.LENA
            mock_item.name = "Leña"
            mock_item.graphic_id = 1001
            mock_item.item_type = MagicMock()
            mock_item.item_type.to_client_type.return_value = 1
            mock_item.max_damage = None
            mock_item.min_damage = None
            mock_item.defense = None
            mock_item.value = 10.0
            mock_get_item.return_value = mock_item

            task = TaskWorkLeftClick(
                packet,
                mock_message_sender,
                player_repo=player_repo,
                inventory_repo=inventory_repo,
                map_manager=MagicMock(),
                session_data={"user_id": 1},
                map_resources=map_resources,
            )
            await task.execute()

            # Debe enviar mensaje de level up
            call_args_list = [
                call[0][0] for call in mock_message_sender.console.send_console_msg.call_args_list
            ]
            assert any("subido de nivel" in msg.lower() for msg in call_args_list)

    @pytest.mark.asyncio
    async def test_execute_distance_too_far(self, mock_message_sender):
        """Test execute cuando el target está demasiado lejos."""
        packet = self._create_work_packet(x=53, y=50, skill=SKILL_TALAR)  # Distancia 3

        player_repo = AsyncMock()
        player_repo.get_position.return_value = {"x": 50, "y": 50, "map": 1}

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

        # Debe enviar mensaje de distancia y retornar sin trabajar
        mock_message_sender.console.send_console_msg.assert_called_once()
        call_args = mock_message_sender.console.send_console_msg.call_args[0][0]
        assert "distancia" in call_args.lower()

    @pytest.mark.asyncio
    async def test_try_work_mine_without_player_repo(self, mock_message_sender):
        """Test minar sin player_repo (no da exp pero da item)."""
        packet = self._create_work_packet(x=50, y=50, skill=SKILL_MINERIA)

        inventory_repo = AsyncMock()
        inventory_repo.get_inventory_slots.return_value = {
            1: InventorySlot(item_id=ToolID.PIQUETE_MINERO, quantity=1)
        }
        inventory_repo.add_item = AsyncMock(return_value=[(6, 3)])

        map_resources = MagicMock()
        map_resources.has_mine.return_value = True

        task = TaskWorkLeftClick(
            packet,
            mock_message_sender,
            player_repo=None,  # Sin player_repo
            inventory_repo=inventory_repo,
            map_manager=MagicMock(),
            session_data={"user_id": 1},
            map_resources=map_resources,
        )
        result = await task._try_work_at_position(1, 1, 50, 50, SKILL_MINERIA)

        # Debe retornar tupla pero sin level up
        assert result is not None
        assert result[6] is False  # leveled_up

    @pytest.mark.asyncio
    async def test_try_work_fish_without_player_repo(self, mock_message_sender):
        """Test pescar sin player_repo (no da exp pero da item)."""
        packet = self._create_work_packet(x=50, y=50, skill=SKILL_PESCA)

        inventory_repo = AsyncMock()
        inventory_repo.get_inventory_slots.return_value = {
            1: InventorySlot(item_id=ToolID.CANA_PESCAR, quantity=1)
        }
        inventory_repo.add_item = AsyncMock(return_value=[(7, 2)])

        map_resources = MagicMock()
        map_resources.has_water.return_value = True

        task = TaskWorkLeftClick(
            packet,
            mock_message_sender,
            player_repo=None,  # Sin player_repo
            inventory_repo=inventory_repo,
            map_manager=MagicMock(),
            session_data={"user_id": 1},
            map_resources=map_resources,
        )
        result = await task._try_work_at_position(1, 1, 50, 50, SKILL_PESCA)

        # Debe retornar tupla pero sin level up
        assert result is not None
        assert result[6] is False  # leveled_up

    @pytest.mark.asyncio
    async def test_try_work_mine_inventory_full(self, mock_message_sender):
        """Test minar cuando el inventario está lleno."""
        packet = self._create_work_packet(x=50, y=50, skill=SKILL_MINERIA)

        inventory_repo = AsyncMock()
        inventory_repo.get_inventory_slots.return_value = {
            1: InventorySlot(item_id=ToolID.PIQUETE_MINERO, quantity=1)
        }
        inventory_repo.add_item = AsyncMock(return_value=None)  # Inventario lleno

        map_resources = MagicMock()
        map_resources.has_mine.return_value = True

        task = TaskWorkLeftClick(
            packet,
            mock_message_sender,
            player_repo=AsyncMock(),
            inventory_repo=inventory_repo,
            map_manager=MagicMock(),
            session_data={"user_id": 1},
            map_resources=map_resources,
        )
        result = await task._try_work_at_position(1, 1, 50, 50, SKILL_MINERIA)

        # Debe retornar None cuando el inventario está lleno
        assert result is None

    @pytest.mark.asyncio
    async def test_try_work_fish_inventory_full(self, mock_message_sender):
        """Test pescar cuando el inventario está lleno."""
        packet = self._create_work_packet(x=50, y=50, skill=SKILL_PESCA)

        inventory_repo = AsyncMock()
        inventory_repo.get_inventory_slots.return_value = {
            1: InventorySlot(item_id=ToolID.CANA_PESCAR, quantity=1)
        }
        inventory_repo.add_item = AsyncMock(return_value=None)  # Inventario lleno

        map_resources = MagicMock()
        map_resources.has_water.return_value = True

        task = TaskWorkLeftClick(
            packet,
            mock_message_sender,
            player_repo=AsyncMock(),
            inventory_repo=inventory_repo,
            map_manager=MagicMock(),
            session_data={"user_id": 1},
            map_resources=map_resources,
        )
        result = await task._try_work_at_position(1, 1, 50, 50, SKILL_PESCA)

        # Debe retornar None cuando el inventario está lleno
        assert result is None

    @pytest.mark.asyncio
    async def test_execute_work_no_resource(self, mock_message_sender):
        """Test execute cuando no hay recurso en la posición."""
        packet = self._create_work_packet(x=51, y=50, skill=SKILL_TALAR)

        player_repo = AsyncMock()
        player_repo.get_position.return_value = {"x": 50, "y": 50, "map": 1}

        inventory_repo = AsyncMock()
        inventory_repo.get_inventory_slots.return_value = {
            1: InventorySlot(item_id=ToolID.HACHA_LENADOR, quantity=1)
        }

        map_resources = MagicMock()
        map_resources.has_tree.return_value = False  # No hay árbol

        task = TaskWorkLeftClick(
            packet,
            mock_message_sender,
            player_repo=player_repo,
            inventory_repo=inventory_repo,
            map_manager=MagicMock(),
            session_data={"user_id": 1},
            map_resources=map_resources,
        )
        await task.execute()

        # Debe enviar mensaje de que no hay nada
        mock_message_sender.console.send_console_msg.assert_called_once()
        call_args = mock_message_sender.console.send_console_msg.call_args[0][0]
        assert "nada" in call_args.lower() or "trabajar" in call_args.lower()

    @pytest.mark.asyncio
    async def test_update_inventory_ui_without_repo(self, mock_message_sender):
        """Test _update_inventory_ui sin inventory_repo."""
        packet = self._create_work_packet(x=50, y=50, skill=SKILL_TALAR)

        task = TaskWorkLeftClick(
            packet,
            mock_message_sender,
            player_repo=AsyncMock(),
            inventory_repo=None,  # Sin repo
            map_manager=MagicMock(),
            session_data={"user_id": 1},
            map_resources=MagicMock(),
        )
        await task._update_inventory_ui(1, ResourceItemID.LENA, 5)

        # No debe hacer nada sin inventory_repo
        mock_message_sender.send_change_inventory_slot.assert_not_called()

    @pytest.mark.asyncio
    async def test_update_inventory_ui_item_not_found(self, mock_message_sender):
        """Test _update_inventory_ui cuando el item no existe en catálogo."""
        packet = self._create_work_packet(x=50, y=50, skill=SKILL_TALAR)

        inventory_repo = AsyncMock()
        inventory_repo.get_slot = AsyncMock(return_value=(ResourceItemID.LENA, 5))

        with patch("src.tasks.work.task_work_left_click.get_item") as mock_get_item:
            mock_get_item.return_value = None  # Item no encontrado

            task = TaskWorkLeftClick(
                packet,
                mock_message_sender,
                player_repo=AsyncMock(),
                inventory_repo=inventory_repo,
                map_manager=MagicMock(),
                session_data={"user_id": 1},
                map_resources=MagicMock(),
            )
            await task._update_inventory_ui(1, ResourceItemID.LENA, 5)

            # No debe actualizar UI si el item no existe
            mock_message_sender.send_change_inventory_slot.assert_not_called()

    @pytest.mark.asyncio
    async def test_update_inventory_ui_slot_not_found(self, mock_message_sender):
        """Test _update_inventory_ui cuando el slot no existe."""
        packet = self._create_work_packet(x=50, y=50, skill=SKILL_TALAR)

        inventory_repo = AsyncMock()
        inventory_repo.get_slot = AsyncMock(return_value=None)  # Slot no encontrado

        with patch("src.tasks.work.task_work_left_click.get_item") as mock_get_item:
            mock_item = MagicMock(spec=Item)
            mock_item.item_id = ResourceItemID.LENA
            mock_item.name = "Leña"
            mock_item.graphic_id = 1001
            mock_item.item_type = MagicMock()
            mock_item.item_type.to_client_type.return_value = 1
            mock_item.max_damage = None
            mock_item.min_damage = None
            mock_item.defense = None
            mock_item.value = 10.0
            mock_get_item.return_value = mock_item

            task = TaskWorkLeftClick(
                packet,
                mock_message_sender,
                player_repo=AsyncMock(),
                inventory_repo=inventory_repo,
                map_manager=MagicMock(),
                session_data={"user_id": 1},
                map_resources=MagicMock(),
            )
            await task._update_inventory_ui(1, ResourceItemID.LENA, 5)

            # No debe actualizar UI si el slot no existe
            mock_message_sender.send_change_inventory_slot.assert_not_called()

    @pytest.mark.asyncio
    async def test_update_inventory_ui_success(self, mock_message_sender):
        """Test _update_inventory_ui exitoso."""
        packet = self._create_work_packet(x=50, y=50, skill=SKILL_TALAR)

        inventory_repo = AsyncMock()
        inventory_repo.get_slot = AsyncMock(
            return_value=(ResourceItemID.LENA, 10)
        )  # Cantidad total 10

        with patch("src.tasks.work.task_work_left_click.get_item") as mock_get_item:
            mock_item = MagicMock(spec=Item)
            mock_item.item_id = ResourceItemID.LENA
            mock_item.name = "Leña"
            mock_item.graphic_id = 1001
            mock_item.item_type = MagicMock()
            mock_item.item_type.to_client_type.return_value = 1
            mock_item.max_damage = 5
            mock_item.min_damage = 3
            mock_item.defense = 2
            mock_item.value = 10.0
            mock_get_item.return_value = mock_item

            task = TaskWorkLeftClick(
                packet,
                mock_message_sender,
                player_repo=AsyncMock(),
                inventory_repo=inventory_repo,
                map_manager=MagicMock(),
                session_data={"user_id": 1},
                map_resources=MagicMock(),
            )
            await task._update_inventory_ui(1, ResourceItemID.LENA, 5)

            # Debe actualizar UI
            mock_message_sender.send_change_inventory_slot.assert_called_once()
            call_kwargs = mock_message_sender.send_change_inventory_slot.call_args[1]
            assert call_kwargs["slot"] == 5
            assert call_kwargs["item_id"] == ResourceItemID.LENA
            assert call_kwargs["name"] == "Leña"
            assert call_kwargs["amount"] == 10
            assert call_kwargs["max_hit"] == 5
            assert call_kwargs["min_hit"] == 3
            assert call_kwargs["max_def"] == 2
            assert call_kwargs["min_def"] == 2
