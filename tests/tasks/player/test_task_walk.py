"""Tests para TaskWalk."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.commands.base import CommandResult
from src.commands.walk_command import WalkCommand
from src.tasks.player.task_walk import TaskWalk


def create_mock_walk_handler(
    player_repo: MagicMock | None = None,
    map_manager: MagicMock | None = None,
    broadcast_service: MagicMock | None = None,
    stamina_service: MagicMock | None = None,
    player_map_service: MagicMock | None = None,
    inventory_repo: MagicMock | None = None,
    map_resources: MagicMock | None = None,
    message_sender: MagicMock | None = None,
) -> MagicMock:
    """Crea un mock de WalkCommandHandler con las dependencias especificadas."""
    handler = MagicMock()
    handler.player_repo = player_repo or MagicMock()
    handler.map_manager = map_manager or MagicMock()
    handler.broadcast_service = broadcast_service
    handler.stamina_service = stamina_service
    handler.player_map_service = player_map_service
    handler.inventory_repo = inventory_repo
    handler.map_resources = map_resources
    handler.message_sender = message_sender or MagicMock()
    handler.handle = AsyncMock()
    return handler


@pytest.mark.asyncio
class TestTaskWalk:
    """Tests para TaskWalk."""

    async def test_walk_north_success(self) -> None:
        """Test de movimiento exitoso hacia el norte."""
        # Setup
        message_sender = MagicMock()
        message_sender.connection.address = "127.0.0.1:1234"

        walk_handler = create_mock_walk_handler(message_sender=message_sender)
        walk_handler.handle.return_value = CommandResult.ok(
            data={"moved": True, "new_x": 50, "new_y": 49, "map": 1, "heading": 1}
        )

        # Packet: WALK + NORTH (1)
        data = bytes([0x06, 0x01])
        session_data = {"user_id": 1}

        task = TaskWalk(
            data,
            message_sender,
            walk_handler=walk_handler,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert
        walk_handler.handle.assert_called_once()
        call_args = walk_handler.handle.call_args[0][0]
        assert isinstance(call_args, WalkCommand)
        assert call_args.user_id == 1
        assert call_args.heading == 1

    async def test_walk_south_success(self) -> None:
        """Test de movimiento exitoso hacia el sur."""
        # Setup
        message_sender = MagicMock()
        message_sender.connection.address = "127.0.0.1:1234"

        walk_handler = create_mock_walk_handler(message_sender=message_sender)
        walk_handler.handle.return_value = CommandResult.ok(
            data={"moved": True, "new_x": 50, "new_y": 51, "map": 1, "heading": 3}
        )

        # Packet: WALK + SOUTH (3)
        data = bytes([0x06, 0x03])
        session_data = {"user_id": 1}

        task = TaskWalk(
            data,
            message_sender,
            walk_handler=walk_handler,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert
        walk_handler.handle.assert_called_once()
        call_args = walk_handler.handle.call_args[0][0]
        assert isinstance(call_args, WalkCommand)
        assert call_args.user_id == 1
        assert call_args.heading == 3

    async def test_walk_east_success(self) -> None:
        """Test de movimiento exitoso hacia el este."""
        # Setup
        message_sender = MagicMock()
        message_sender.connection.address = "127.0.0.1:1234"

        walk_handler = create_mock_walk_handler(message_sender=message_sender)
        walk_handler.handle.return_value = CommandResult.ok(
            data={"moved": True, "new_x": 51, "new_y": 50, "map": 1, "heading": 2}
        )

        # Packet: WALK + EAST (2)
        data = bytes([0x06, 0x02])
        session_data = {"user_id": 1}

        task = TaskWalk(
            data,
            message_sender,
            walk_handler=walk_handler,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert
        walk_handler.handle.assert_called_once()
        call_args = walk_handler.handle.call_args[0][0]
        assert isinstance(call_args, WalkCommand)
        assert call_args.user_id == 1
        assert call_args.heading == 2

    async def test_walk_west_success(self) -> None:
        """Test de movimiento exitoso hacia el oeste."""
        # Setup
        message_sender = MagicMock()
        message_sender.connection.address = "127.0.0.1:1234"

        walk_handler = create_mock_walk_handler(message_sender=message_sender)
        walk_handler.handle.return_value = CommandResult.ok(
            data={"moved": True, "new_x": 49, "new_y": 50, "map": 1, "heading": 4}
        )

        # Packet: WALK + WEST (4)
        data = bytes([0x06, 0x04])
        session_data = {"user_id": 1}

        task = TaskWalk(
            data,
            message_sender,
            walk_handler=walk_handler,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert
        walk_handler.handle.assert_called_once()
        call_args = walk_handler.handle.call_args[0][0]
        assert isinstance(call_args, WalkCommand)
        assert call_args.user_id == 1
        assert call_args.heading == 4

    async def test_walk_blocked_by_wall(self) -> None:
        """Test de movimiento bloqueado por pared."""
        # Setup
        message_sender = MagicMock()
        message_sender.connection.address = "127.0.0.1:1234"

        walk_handler = create_mock_walk_handler(message_sender=message_sender)
        walk_handler.handle.return_value = CommandResult.ok(data={"moved": False, "blocked": True})

        data = bytes([0x06, 0x01])  # NORTH
        session_data = {"user_id": 1}

        task = TaskWalk(
            data,
            message_sender,
            walk_handler=walk_handler,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert
        walk_handler.handle.assert_called_once()
        call_args = walk_handler.handle.call_args[0][0]
        assert isinstance(call_args, WalkCommand)
        assert call_args.heading == 1

    async def test_walk_triggers_exit_transition(self) -> None:
        """Test que caminar hacia un exit tile dispara transition_to_map."""
        # Setup
        message_sender = MagicMock()
        message_sender.connection.address = "127.0.0.1:1234"

        walk_handler = create_mock_walk_handler(message_sender=message_sender)
        walk_handler.handle.return_value = CommandResult.ok(
            data={
                "moved": True,
                "changed_map": True,
                "new_map": 2,
                "new_x": 50,
                "new_y": 99,
            }
        )

        # Packet: WALK + SOUTH (3)
        data = bytes([0x06, 0x03])
        session_data = {"user_id": 1}

        task = TaskWalk(
            data,
            message_sender,
            walk_handler=walk_handler,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert
        walk_handler.handle.assert_called_once()
        call_args = walk_handler.handle.call_args[0][0]
        assert isinstance(call_args, WalkCommand)
        assert call_args.heading == 3

    async def test_walk_at_map_edge_north(self) -> None:
        """Test de movimiento en el borde norte del mapa."""
        # Setup
        message_sender = MagicMock()
        message_sender.connection.address = "127.0.0.1:1234"

        walk_handler = create_mock_walk_handler(message_sender=message_sender)
        walk_handler.handle.return_value = CommandResult.ok(
            data={"moved": False, "heading_changed": True}
        )

        data = bytes([0x06, 0x01])  # NORTH
        session_data = {"user_id": 1}

        task = TaskWalk(
            data,
            message_sender,
            walk_handler=walk_handler,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert
        walk_handler.handle.assert_called_once()
        call_args = walk_handler.handle.call_args[0][0]
        assert isinstance(call_args, WalkCommand)
        assert call_args.heading == 1

    async def test_walk_cancels_meditation(self) -> None:
        """Test que el movimiento cancela la meditación."""
        # Setup
        message_sender = MagicMock()
        message_sender.connection.address = "127.0.0.1:1234"
        message_sender.send_meditate_toggle = AsyncMock()
        message_sender.send_console_msg = AsyncMock()

        walk_handler = create_mock_walk_handler(message_sender=message_sender)
        walk_handler.handle.return_value = CommandResult.ok(
            data={"moved": True, "new_x": 50, "new_y": 49, "map": 1, "heading": 1}
        )

        data = bytes([0x06, 0x01])
        session_data = {"user_id": 1}

        task = TaskWalk(
            data,
            message_sender,
            walk_handler=walk_handler,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert - el handler debe ser llamado (la cancelación de meditación está en el handler)
        walk_handler.handle.assert_called_once()

    async def test_walk_invalid_packet_size(self) -> None:
        """Test con packet de tamaño inválido."""
        # Setup
        message_sender = MagicMock()
        message_sender.connection.address = "127.0.0.1:1234"

        walk_handler = create_mock_walk_handler(message_sender=message_sender)

        # Packet muy corto
        data = bytes([0x06])  # Falta dirección

        session_data = {"user_id": 1}

        task = TaskWalk(
            data,
            message_sender,
            walk_handler=walk_handler,
            session_data=session_data,
        )

        # Execute - debe manejar la excepción sin crashear
        await task.execute()

        # Assert - no debe llamar al handler si el packet es inválido
        walk_handler.handle.assert_not_called()

    async def test_walk_invalid_direction(self) -> None:
        """Test con dirección inválida."""
        # Setup
        message_sender = MagicMock()
        message_sender.connection.address = "127.0.0.1:1234"

        walk_handler = create_mock_walk_handler(message_sender=message_sender)

        # Packet con dirección inválida (5)
        data = bytes([0x06, 0x05])

        session_data = {"user_id": 1}

        task = TaskWalk(
            data,
            message_sender,
            walk_handler=walk_handler,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert - no debe hacer nada
        walk_handler.handle.assert_not_called()

    async def test_walk_without_walk_handler(self) -> None:
        """Test sin handler de movimiento."""
        # Setup
        message_sender = MagicMock()
        message_sender.connection.address = "127.0.0.1:1234"

        data = bytes([0x06, 0x01])
        session_data = {"user_id": 1}

        task = TaskWalk(
            data,
            message_sender,
            walk_handler=None,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert - no debe crashear

    async def test_walk_without_session(self) -> None:
        """Test sin sesión activa."""
        # Setup
        message_sender = MagicMock()
        message_sender.connection.address = "127.0.0.1:1234"

        walk_handler = create_mock_walk_handler(message_sender=message_sender)

        data = bytes([0x06, 0x01])
        session_data = {}  # Sin user_id

        task = TaskWalk(
            data,
            message_sender,
            walk_handler=walk_handler,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert
        walk_handler.handle.assert_not_called()

    async def test_walk_with_dict_user_id(self) -> None:
        """Test con user_id como dict (inválido)."""
        # Setup
        message_sender = MagicMock()
        message_sender.connection.address = "127.0.0.1:1234"

        walk_handler = create_mock_walk_handler(message_sender=message_sender)

        data = bytes([0x06, 0x01])
        session_data = {"user_id": {"invalid": "data"}}

        task = TaskWalk(
            data,
            message_sender,
            walk_handler=walk_handler,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert
        walk_handler.handle.assert_not_called()

    async def test_walk_position_not_found(self) -> None:
        """Test cuando no se encuentra la posición del jugador."""
        # Setup
        message_sender = MagicMock()
        message_sender.connection.address = "127.0.0.1:1234"

        walk_handler = create_mock_walk_handler(message_sender=message_sender)
        walk_handler.handle.return_value = CommandResult.error("Posición no encontrada")

        data = bytes([0x06, 0x01])
        session_data = {"user_id": 1}

        task = TaskWalk(
            data,
            message_sender,
            walk_handler=walk_handler,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert
        walk_handler.handle.assert_called_once()

    async def test_walk_with_stamina_service(self) -> None:
        """Test de movimiento con servicio de stamina."""
        message_sender = MagicMock()
        message_sender.connection.address = "127.0.0.1:1234"

        walk_handler = create_mock_walk_handler(message_sender=message_sender)
        walk_handler.handle.return_value = CommandResult.ok(
            data={"moved": True, "new_x": 50, "new_y": 49, "map": 1, "heading": 1}
        )

        data = bytes([0x06, 0x01])
        session_data = {"user_id": 1}

        task = TaskWalk(
            data,
            message_sender,
            walk_handler=walk_handler,
            session_data=session_data,
        )

        await task.execute()

        # Verificar que se llamó al handler (el consumo de stamina está en el handler)
        walk_handler.handle.assert_called_once()

    async def test_walk_insufficient_stamina(self) -> None:
        """Test cuando no hay suficiente stamina."""
        message_sender = MagicMock()
        message_sender.connection.address = "127.0.0.1:1234"

        walk_handler = create_mock_walk_handler(message_sender=message_sender)
        walk_handler.handle.return_value = CommandResult.error(
            "No tienes suficiente stamina para moverte."
        )

        data = bytes([0x06, 0x01])
        session_data = {"user_id": 1}

        task = TaskWalk(
            data,
            message_sender,
            walk_handler=walk_handler,
            session_data=session_data,
        )

        await task.execute()

        # El handler debe ser llamado (la validación de stamina está en el handler)
        walk_handler.handle.assert_called_once()

    async def test_walk_at_map_edge_south(self) -> None:
        """Test de movimiento en el borde sur del mapa."""
        message_sender = MagicMock()
        message_sender.connection.address = "127.0.0.1:1234"

        walk_handler = create_mock_walk_handler(message_sender=message_sender)
        walk_handler.handle.return_value = CommandResult.ok(
            data={"moved": False, "heading_changed": True}
        )

        data = bytes([0x06, 0x03])  # SOUTH
        session_data = {"user_id": 1}

        task = TaskWalk(
            data,
            message_sender,
            walk_handler=walk_handler,
            session_data=session_data,
        )

        await task.execute()

        # Assert
        walk_handler.handle.assert_called_once()
        call_args = walk_handler.handle.call_args[0][0]
        assert isinstance(call_args, WalkCommand)
        assert call_args.heading == 3

    async def test_walk_blocked_by_player(self) -> None:
        """Test de movimiento bloqueado por otro jugador."""
        message_sender = MagicMock()
        message_sender.connection.address = "127.0.0.1:1234"

        walk_handler = create_mock_walk_handler(message_sender=message_sender)
        walk_handler.handle.return_value = CommandResult.ok(data={"moved": False, "blocked": True})

        data = bytes([0x06, 0x01])  # NORTH
        session_data = {"user_id": 1}

        task = TaskWalk(
            data,
            message_sender,
            walk_handler=walk_handler,
            session_data=session_data,
        )

        await task.execute()

        # Assert
        walk_handler.handle.assert_called_once()
        call_args = walk_handler.handle.call_args[0][0]
        assert isinstance(call_args, WalkCommand)
        assert call_args.heading == 1

    async def test_walk_blocked_by_npc(self) -> None:
        """Test de movimiento bloqueado por NPC."""
        message_sender = MagicMock()
        message_sender.connection.address = "127.0.0.1:1234"

        walk_handler = create_mock_walk_handler(message_sender=message_sender)
        walk_handler.handle.return_value = CommandResult.ok(data={"moved": False, "blocked": True})

        data = bytes([0x06, 0x02])  # EAST
        session_data = {"user_id": 1}

        task = TaskWalk(
            data,
            message_sender,
            walk_handler=walk_handler,
            session_data=session_data,
        )

        await task.execute()

        # Assert
        walk_handler.handle.assert_called_once()
        call_args = walk_handler.handle.call_args[0][0]
        assert isinstance(call_args, WalkCommand)
        assert call_args.heading == 2
