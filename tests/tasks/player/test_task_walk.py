"""Tests para TaskWalk."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.game.map_manager import MapManager
from src.repositories.player_repository import PlayerRepository
from src.services.multiplayer_broadcast_service import MultiplayerBroadcastService
from src.tasks.player.task_walk import TaskWalk


@pytest.mark.asyncio
class TestTaskWalk:
    """Tests para TaskWalk."""

    async def test_walk_north_success(self) -> None:
        """Test de movimiento exitoso hacia el norte."""
        # Setup
        message_sender = MagicMock()
        message_sender.connection.address = "127.0.0.1:1234"

        player_repo = MagicMock(spec=PlayerRepository)
        player_repo.is_meditating = AsyncMock(return_value=False)
        player_repo.get_position = AsyncMock(
            return_value={"x": 50, "y": 50, "map": 1, "heading": 3}
        )
        player_repo.set_position = AsyncMock()

        map_manager = MagicMock(spec=MapManager)
        map_manager.can_move_to = MagicMock(return_value=True)
        map_manager.update_player_tile = MagicMock()
        map_manager.get_map_size = MagicMock(return_value=(100, 100))
        map_manager.get_exit_tile = MagicMock(return_value=None)

        broadcast_service = MagicMock(spec=MultiplayerBroadcastService)
        broadcast_service.broadcast_character_move = AsyncMock()

        # Packet: WALK + NORTH (1)
        data = bytes([0x06, 0x01])

        session_data = {"user_id": 1}

        task = TaskWalk(
            data,
            message_sender,
            player_repo=player_repo,
            map_manager=map_manager,
            broadcast_service=broadcast_service,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert
        player_repo.set_position.assert_called_once_with(1, 50, 49, 1, 1)  # y-1
        map_manager.update_player_tile.assert_called_once_with(1, 1, 50, 50, 50, 49)
        broadcast_service.broadcast_character_move.assert_called_once()

    async def test_walk_south_success(self) -> None:
        """Test de movimiento exitoso hacia el sur."""
        # Setup
        message_sender = MagicMock()
        message_sender.connection.address = "127.0.0.1:1234"

        player_repo = MagicMock(spec=PlayerRepository)
        player_repo.is_meditating = AsyncMock(return_value=False)
        player_repo.get_position = AsyncMock(
            return_value={"x": 50, "y": 50, "map": 1, "heading": 1}
        )
        player_repo.set_position = AsyncMock()

        map_manager = MagicMock(spec=MapManager)
        map_manager.can_move_to = MagicMock(return_value=True)
        map_manager.update_player_tile = MagicMock()
        map_manager.get_map_size = MagicMock(return_value=(100, 100))
        map_manager.get_exit_tile = MagicMock(return_value=None)  # No hay exit tile

        broadcast_service = MagicMock(spec=MultiplayerBroadcastService)
        broadcast_service.broadcast_character_move = AsyncMock()

        # Packet: WALK + SOUTH (3)
        data = bytes([0x06, 0x03])

        session_data = {"user_id": 1}

        task = TaskWalk(
            data,
            message_sender,
            player_repo=player_repo,
            map_manager=map_manager,
            broadcast_service=broadcast_service,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert
        player_repo.set_position.assert_called_once_with(1, 50, 51, 1, 3)  # y+1

    async def test_walk_east_success(self) -> None:
        """Test de movimiento exitoso hacia el este."""
        # Setup
        message_sender = MagicMock()
        message_sender.connection.address = "127.0.0.1:1234"

        player_repo = MagicMock(spec=PlayerRepository)
        player_repo.is_meditating = AsyncMock(return_value=False)
        player_repo.get_position = AsyncMock(
            return_value={"x": 50, "y": 50, "map": 1, "heading": 4}
        )
        player_repo.set_position = AsyncMock()

        map_manager = MagicMock(spec=MapManager)
        map_manager.can_move_to = MagicMock(return_value=True)
        map_manager.update_player_tile = MagicMock()
        map_manager.get_map_size = MagicMock(return_value=(100, 100))
        map_manager.get_exit_tile = MagicMock(return_value=None)

        broadcast_service = MagicMock(spec=MultiplayerBroadcastService)
        broadcast_service.broadcast_character_move = AsyncMock()

        # Packet: WALK + EAST (2)
        data = bytes([0x06, 0x02])

        session_data = {"user_id": 1}

        task = TaskWalk(
            data,
            message_sender,
            player_repo=player_repo,
            map_manager=map_manager,
            broadcast_service=broadcast_service,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert
        player_repo.set_position.assert_called_once_with(1, 51, 50, 1, 2)  # x+1

    async def test_walk_west_success(self) -> None:
        """Test de movimiento exitoso hacia el oeste."""
        # Setup
        message_sender = MagicMock()
        message_sender.connection.address = "127.0.0.1:1234"

        player_repo = MagicMock(spec=PlayerRepository)
        player_repo.is_meditating = AsyncMock(return_value=False)
        player_repo.get_position = AsyncMock(
            return_value={"x": 50, "y": 50, "map": 1, "heading": 2}
        )
        player_repo.set_position = AsyncMock()

        map_manager = MagicMock(spec=MapManager)
        map_manager.can_move_to = MagicMock(return_value=True)
        map_manager.update_player_tile = MagicMock()
        map_manager.get_map_size = MagicMock(return_value=(100, 100))
        map_manager.get_exit_tile = MagicMock(return_value=None)

        broadcast_service = MagicMock(spec=MultiplayerBroadcastService)
        broadcast_service.broadcast_character_move = AsyncMock()

        # Packet: WALK + WEST (4)
        data = bytes([0x06, 0x04])

        session_data = {"user_id": 1}

        task = TaskWalk(
            data,
            message_sender,
            player_repo=player_repo,
            map_manager=map_manager,
            broadcast_service=broadcast_service,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert
        player_repo.set_position.assert_called_once_with(1, 49, 50, 1, 4)  # x-1

    async def test_walk_blocked_by_wall(self) -> None:
        """Test de movimiento bloqueado por pared."""
        # Setup
        message_sender = MagicMock()
        message_sender.connection.address = "127.0.0.1:1234"

        player_repo = MagicMock(spec=PlayerRepository)
        player_repo.is_meditating = AsyncMock(return_value=False)
        player_repo.get_position = AsyncMock(
            return_value={"x": 50, "y": 50, "map": 1, "heading": 3}
        )
        player_repo.set_position = AsyncMock()
        player_repo.set_heading = AsyncMock()

        map_manager = MagicMock(spec=MapManager)
        map_manager.can_move_to = MagicMock(return_value=False)  # Bloqueado
        map_manager.get_map_size = MagicMock(return_value=(100, 100))
        map_manager.get_exit_tile = MagicMock(return_value=None)
        map_manager._blocked_tiles = {1: {(50, 49)}}  # noqa: SLF001

        broadcast_service = MagicMock(spec=MultiplayerBroadcastService)

        data = bytes([0x06, 0x01])  # NORTH
        session_data = {"user_id": 1}

        task = TaskWalk(
            data,
            message_sender,
            player_repo=player_repo,
            map_manager=map_manager,
            broadcast_service=broadcast_service,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert - no debe moverse, solo cambiar dirección
        player_repo.set_position.assert_not_called()
        player_repo.set_heading.assert_called_once_with(1, 1)

    async def test_walk_at_map_edge_north(self) -> None:
        """Test de movimiento en el borde norte del mapa."""
        # Setup
        message_sender = MagicMock()
        message_sender.connection.address = "127.0.0.1:1234"

        player_repo = MagicMock(spec=PlayerRepository)
        player_repo.is_meditating = AsyncMock(return_value=False)
        player_repo.get_position = AsyncMock(
            return_value={"x": 50, "y": 1, "map": 1, "heading": 3}  # En el borde
        )
        player_repo.set_position = AsyncMock()
        player_repo.set_heading = AsyncMock()

        map_manager = MagicMock(spec=MapManager)
        map_manager.get_map_size = MagicMock(return_value=(100, 100))
        map_manager.get_exit_tile = MagicMock(return_value=None)
        broadcast_service = MagicMock(spec=MultiplayerBroadcastService)

        data = bytes([0x06, 0x01])  # NORTH
        session_data = {"user_id": 1}

        task = TaskWalk(
            data,
            message_sender,
            player_repo=player_repo,
            map_manager=map_manager,
            broadcast_service=broadcast_service,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert - no debe moverse (ya está en y=1)
        player_repo.set_position.assert_not_called()
        player_repo.set_heading.assert_called_once_with(1, 1)

    async def test_walk_cancels_meditation(self) -> None:
        """Test que el movimiento cancela la meditación."""
        # Setup
        message_sender = MagicMock()
        message_sender.connection.address = "127.0.0.1:1234"
        message_sender.send_meditate_toggle = AsyncMock()
        message_sender.send_console_msg = AsyncMock()

        player_repo = MagicMock(spec=PlayerRepository)
        player_repo.is_meditating = AsyncMock(return_value=True)  # Está meditando
        player_repo.set_meditating = AsyncMock()
        player_repo.get_position = AsyncMock(
            return_value={"x": 50, "y": 50, "map": 1, "heading": 3}
        )
        player_repo.set_position = AsyncMock()

        map_manager = MagicMock(spec=MapManager)
        map_manager.can_move_to = MagicMock(return_value=True)
        map_manager.update_player_tile = MagicMock()
        map_manager.get_map_size = MagicMock(return_value=(100, 100))

        broadcast_service = MagicMock(spec=MultiplayerBroadcastService)
        broadcast_service.broadcast_character_move = AsyncMock()

        data = bytes([0x06, 0x01])
        session_data = {"user_id": 1}

        task = TaskWalk(
            data,
            message_sender,
            player_repo=player_repo,
            map_manager=map_manager,
            broadcast_service=broadcast_service,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert
        player_repo.set_meditating.assert_called_once_with(1, is_meditating=False)
        message_sender.send_meditate_toggle.assert_called_once()
        message_sender.send_console_msg.assert_called_once_with("Dejas de meditar al moverte.")

    async def test_walk_invalid_packet_size(self) -> None:
        """Test con packet de tamaño inválido."""
        # Setup
        message_sender = MagicMock()
        message_sender.connection.address = "127.0.0.1:1234"

        player_repo = MagicMock(spec=PlayerRepository)

        # Packet muy corto
        data = bytes([0x06])  # Falta dirección

        session_data = {"user_id": 1}

        task = TaskWalk(
            data,
            message_sender,
            player_repo=player_repo,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert - no debe hacer nada
        player_repo.get_position.assert_not_called()

    async def test_walk_invalid_direction(self) -> None:
        """Test con dirección inválida."""
        # Setup
        message_sender = MagicMock()
        message_sender.connection.address = "127.0.0.1:1234"

        player_repo = MagicMock(spec=PlayerRepository)

        # Packet con dirección inválida (5)
        data = bytes([0x06, 0x05])

        session_data = {"user_id": 1}

        task = TaskWalk(
            data,
            message_sender,
            player_repo=player_repo,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert - no debe hacer nada
        player_repo.get_position.assert_not_called()

    async def test_walk_without_player_repo(self) -> None:
        """Test sin repositorio de jugadores."""
        # Setup
        message_sender = MagicMock()
        message_sender.connection.address = "127.0.0.1:1234"

        data = bytes([0x06, 0x01])
        session_data = {"user_id": 1}

        task = TaskWalk(data, message_sender, player_repo=None, session_data=session_data)

        # Execute
        await task.execute()

        # Assert - no debe crashear

    async def test_walk_without_session(self) -> None:
        """Test sin sesión activa."""
        # Setup
        message_sender = MagicMock()
        message_sender.connection.address = "127.0.0.1:1234"

        player_repo = MagicMock(spec=PlayerRepository)

        data = bytes([0x06, 0x01])
        session_data = {}  # Sin user_id

        task = TaskWalk(
            data,
            message_sender,
            player_repo=player_repo,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert
        player_repo.get_position.assert_not_called()

    async def test_walk_with_dict_user_id(self) -> None:
        """Test con user_id como dict (inválido)."""
        # Setup
        message_sender = MagicMock()
        message_sender.connection.address = "127.0.0.1:1234"

        player_repo = MagicMock(spec=PlayerRepository)

        data = bytes([0x06, 0x01])
        session_data = {"user_id": {"invalid": "data"}}

        task = TaskWalk(
            data,
            message_sender,
            player_repo=player_repo,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert
        player_repo.get_position.assert_not_called()

    async def test_walk_position_not_found(self) -> None:
        """Test cuando no se encuentra la posición del jugador."""
        # Setup
        message_sender = MagicMock()
        message_sender.connection.address = "127.0.0.1:1234"

        player_repo = MagicMock(spec=PlayerRepository)
        player_repo.is_meditating = AsyncMock(return_value=False)
        player_repo.get_position = AsyncMock(return_value=None)  # No encontrado

        data = bytes([0x06, 0x01])
        session_data = {"user_id": 1}

        task = TaskWalk(
            data,
            message_sender,
            player_repo=player_repo,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert
        player_repo.set_position.assert_not_called()

    async def test_walk_with_stamina_service(self) -> None:
        """Test de movimiento con servicio de stamina."""
        message_sender = MagicMock()
        message_sender.connection.address = "127.0.0.1:1234"

        player_repo = MagicMock(spec=PlayerRepository)
        player_repo.is_meditating = AsyncMock(return_value=False)
        player_repo.get_position = AsyncMock(
            return_value={"x": 50, "y": 50, "map": 1, "heading": 3}
        )
        player_repo.set_position = AsyncMock()

        stamina_service = MagicMock()
        stamina_service.consume_stamina = AsyncMock(return_value=True)

        map_manager = MagicMock(spec=MapManager)
        map_manager.can_move_to = MagicMock(return_value=True)
        map_manager.update_player_tile = MagicMock()
        map_manager.get_map_size = MagicMock(return_value=(100, 100))
        map_manager.get_exit_tile = MagicMock(return_value=None)

        broadcast_service = MagicMock(spec=MultiplayerBroadcastService)
        broadcast_service.broadcast_character_move = AsyncMock()

        data = bytes([0x06, 0x01])
        session_data = {"user_id": 1}

        task = TaskWalk(
            data,
            message_sender,
            player_repo=player_repo,
            map_manager=map_manager,
            broadcast_service=broadcast_service,
            stamina_service=stamina_service,
            session_data=session_data,
        )

        await task.execute()

        # Verificar que se consumió stamina
        stamina_service.consume_stamina.assert_called_once()
        player_repo.set_position.assert_called_once()

    async def test_walk_insufficient_stamina(self) -> None:
        """Test cuando no hay suficiente stamina."""
        message_sender = MagicMock()
        message_sender.connection.address = "127.0.0.1:1234"

        player_repo = MagicMock(spec=PlayerRepository)
        player_repo.is_meditating = AsyncMock(return_value=False)

        stamina_service = MagicMock()
        stamina_service.consume_stamina = AsyncMock(return_value=False)  # Sin stamina

        data = bytes([0x06, 0x01])
        session_data = {"user_id": 1}

        task = TaskWalk(
            data,
            message_sender,
            player_repo=player_repo,
            stamina_service=stamina_service,
            session_data=session_data,
        )

        await task.execute()

        # No debe intentar obtener posición
        player_repo.get_position.assert_not_called()

    async def test_walk_at_map_edge_south(self) -> None:
        """Test de movimiento en el borde sur del mapa."""
        message_sender = MagicMock()
        message_sender.connection.address = "127.0.0.1:1234"

        player_repo = MagicMock(spec=PlayerRepository)
        player_repo.is_meditating = AsyncMock(return_value=False)
        player_repo.get_position = AsyncMock(
            return_value={"x": 50, "y": 100, "map": 1, "heading": 1}  # En el borde sur
        )
        player_repo.set_heading = AsyncMock()

        map_manager = MagicMock(spec=MapManager)
        map_manager.get_map_size = MagicMock(return_value=(100, 100))
        map_manager.get_exit_tile = MagicMock(return_value=None)

        data = bytes([0x06, 0x03])  # SOUTH
        session_data = {"user_id": 1}

        task = TaskWalk(
            data,
            message_sender,
            player_repo=player_repo,
            map_manager=map_manager,
            session_data=session_data,
        )

        await task.execute()

        # No debe moverse (ya está en y=100)
        player_repo.set_position.assert_not_called()
        player_repo.set_heading.assert_called_once_with(1, 3)

    async def test_walk_blocked_by_player(self) -> None:
        """Test de movimiento bloqueado por otro jugador."""
        message_sender = MagicMock()
        message_sender.connection.address = "127.0.0.1:1234"

        player_repo = MagicMock(spec=PlayerRepository)
        player_repo.is_meditating = AsyncMock(return_value=False)
        player_repo.get_position = AsyncMock(
            return_value={"x": 50, "y": 50, "map": 1, "heading": 3}
        )
        player_repo.set_heading = AsyncMock()

        map_manager = MagicMock(spec=MapManager)
        map_manager.can_move_to = MagicMock(return_value=False)
        map_manager.get_map_size = MagicMock(return_value=(100, 100))
        map_manager.get_exit_tile = MagicMock(return_value=None)
        map_manager._blocked_tiles = {}  # noqa: SLF001
        map_manager.get_tile_occupant = MagicMock(return_value="player:2")

        data = bytes([0x06, 0x01])  # NORTH
        session_data = {"user_id": 1}

        task = TaskWalk(
            data,
            message_sender,
            player_repo=player_repo,
            map_manager=map_manager,
            session_data=session_data,
        )

        await task.execute()

        # No debe moverse, solo cambiar dirección
        player_repo.set_position.assert_not_called()
        player_repo.set_heading.assert_called_once_with(1, 1)

    async def test_walk_blocked_by_npc(self) -> None:
        """Test de movimiento bloqueado por NPC."""
        message_sender = MagicMock()
        message_sender.connection.address = "127.0.0.1:1234"

        player_repo = MagicMock(spec=PlayerRepository)
        player_repo.is_meditating = AsyncMock(return_value=False)
        player_repo.get_position = AsyncMock(
            return_value={"x": 50, "y": 50, "map": 1, "heading": 3}
        )
        player_repo.set_heading = AsyncMock()

        map_manager = MagicMock(spec=MapManager)
        map_manager.can_move_to = MagicMock(return_value=False)
        map_manager.get_map_size = MagicMock(return_value=(100, 100))
        map_manager.get_exit_tile = MagicMock(return_value=None)
        map_manager._blocked_tiles = {}  # noqa: SLF001
        map_manager.get_tile_occupant = MagicMock(return_value="npc:100")

        data = bytes([0x06, 0x02])  # EAST
        session_data = {"user_id": 1}

        task = TaskWalk(
            data,
            message_sender,
            player_repo=player_repo,
            map_manager=map_manager,
            session_data=session_data,
        )

        await task.execute()

        # No debe moverse
        player_repo.set_position.assert_not_called()
        player_repo.set_heading.assert_called_once_with(1, 2)


class TestTaskWalkHelpers:
    """Tests para métodos helper de TaskWalk (síncronos)."""

    def test_get_edge_if_near_border_north(self) -> None:
        """Test de detección de borde norte."""
        edge = TaskWalk._get_edge_if_near_border(  # noqa: SLF001
            heading=1, check_x=50, check_y=5, map_width=100, map_height=100
        )

        assert edge == "north"

    def test_get_edge_if_near_border_east(self) -> None:
        """Test de detección de borde este."""
        edge = TaskWalk._get_edge_if_near_border(  # noqa: SLF001
            heading=2, check_x=95, check_y=50, map_width=100, map_height=100
        )

        assert edge == "east"

    def test_get_edge_if_near_border_south(self) -> None:
        """Test de detección de borde sur."""
        edge = TaskWalk._get_edge_if_near_border(  # noqa: SLF001
            heading=3, check_x=50, check_y=95, map_width=100, map_height=100
        )

        assert edge == "south"

    def test_get_edge_if_near_border_west(self) -> None:
        """Test de detección de borde oeste."""
        edge = TaskWalk._get_edge_if_near_border(  # noqa: SLF001
            heading=4, check_x=5, check_y=50, map_width=100, map_height=100
        )

        assert edge == "west"

    def test_get_edge_if_near_border_not_near(self) -> None:
        """Test cuando no está cerca del borde."""
        edge = TaskWalk._get_edge_if_near_border(  # noqa: SLF001
            heading=1, check_x=50, check_y=50, map_width=100, map_height=100
        )

        assert edge is None
