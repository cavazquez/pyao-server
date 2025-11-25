"""Tests para TaskRequestAttributes."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.commands.base import CommandResult
from src.commands.request_attributes_command import RequestAttributesCommand
from src.tasks.player.task_attributes import TaskRequestAttributes


@pytest.mark.asyncio
class TestTaskRequestAttributes:
    """Tests para TaskRequestAttributes."""

    async def test_send_attributes_from_session(self) -> None:
        """Test de envío de atributos desde sesión (creación de personaje)."""
        # Setup
        message_sender = MagicMock()
        message_sender.send_attributes = AsyncMock()
        message_sender.connection.address = "127.0.0.1:1234"

        # Mock del handler
        request_attributes_handler = MagicMock()
        request_attributes_handler.handle = AsyncMock(
            return_value=CommandResult.ok(
                data={
                    "attributes": {
                        "strength": 18,
                        "agility": 15,
                        "intelligence": 12,
                        "charisma": 10,
                        "constitution": 14,
                    },
                    "from_session": True,
                }
            )
        )

        data = bytes([0x32])  # PacketID REQUEST_ATTRIBUTES

        session_data = {
            "dice_attributes": {
                "strength": 18,
                "agility": 15,
                "intelligence": 12,
                "charisma": 10,
                "constitution": 14,
            }
        }

        task = TaskRequestAttributes(
            data,
            message_sender,
            request_attributes_handler=request_attributes_handler,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert
        request_attributes_handler.handle.assert_called_once()
        call_args = request_attributes_handler.handle.call_args[0][0]
        assert isinstance(call_args, RequestAttributesCommand)
        assert call_args.dice_attributes == session_data["dice_attributes"]
        assert call_args.user_id is None

    async def test_send_attributes_from_repository(self) -> None:
        """Test de envío de atributos desde repositorio."""
        # Setup
        message_sender = MagicMock()
        message_sender.send_attributes = AsyncMock()
        message_sender.connection.address = "127.0.0.1:1234"

        # Mock del handler
        request_attributes_handler = MagicMock()
        request_attributes_handler.handle = AsyncMock(
            return_value=CommandResult.ok(
                data={
                    "user_id": 1,
                    "attributes": {
                        "strength": 20,
                        "agility": 16,
                        "intelligence": 14,
                        "charisma": 12,
                        "constitution": 18,
                    },
                }
            )
        )

        data = bytes([0x32])

        session_data = {"user_id": 1}

        task = TaskRequestAttributes(
            data,
            message_sender,
            request_attributes_handler=request_attributes_handler,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert
        request_attributes_handler.handle.assert_called_once()
        call_args = request_attributes_handler.handle.call_args[0][0]
        assert isinstance(call_args, RequestAttributesCommand)
        assert call_args.user_id == 1
        assert call_args.dice_attributes is None

    async def test_send_attributes_without_repository(self) -> None:
        """Test sin handler disponible."""
        # Setup
        message_sender = MagicMock()
        message_sender.send_attributes = AsyncMock()
        message_sender.connection.address = "127.0.0.1:1234"

        data = bytes([0x32])
        session_data = {"user_id": 1}

        task = TaskRequestAttributes(
            data, message_sender, request_attributes_handler=None, session_data=session_data
        )

        # Execute
        await task.execute()

        # Assert - debe enviar ceros
        message_sender.send_attributes.assert_called_once_with(0, 0, 0, 0, 0)

    async def test_send_attributes_without_user_id(self) -> None:
        """Test sin user_id en sesión."""
        # Setup
        message_sender = MagicMock()
        message_sender.send_attributes = AsyncMock()
        message_sender.connection.address = "127.0.0.1:1234"

        # Mock del handler
        request_attributes_handler = MagicMock()
        request_attributes_handler.handle = AsyncMock()

        data = bytes([0x32])
        session_data = {}  # Sin user_id

        task = TaskRequestAttributes(
            data,
            message_sender,
            request_attributes_handler=request_attributes_handler,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert - debe enviar ceros y no llamar al handler
        message_sender.send_attributes.assert_called_once_with(0, 0, 0, 0, 0)
        request_attributes_handler.handle.assert_not_called()

    async def test_send_attributes_with_dict_user_id(self) -> None:
        """Test con user_id como dict (caso inválido)."""
        # Setup
        message_sender = MagicMock()
        message_sender.send_attributes = AsyncMock()
        message_sender.connection.address = "127.0.0.1:1234"

        # Mock del handler
        request_attributes_handler = MagicMock()
        request_attributes_handler.handle = AsyncMock()

        data = bytes([0x32])
        session_data = {"user_id": {"invalid": "data"}}  # user_id inválido

        task = TaskRequestAttributes(
            data,
            message_sender,
            request_attributes_handler=request_attributes_handler,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert - debe enviar ceros y no llamar al handler
        message_sender.send_attributes.assert_called_once_with(0, 0, 0, 0, 0)
        request_attributes_handler.handle.assert_not_called()

    async def test_send_attributes_not_found_in_repository(self) -> None:
        """Test cuando no se encuentran atributos en el repositorio."""
        # Setup
        message_sender = MagicMock()
        message_sender.send_attributes = AsyncMock()
        message_sender.connection.address = "127.0.0.1:1234"

        # Mock del handler que retorna error
        request_attributes_handler = MagicMock()
        request_attributes_handler.handle = AsyncMock(
            return_value=CommandResult.error("No se encontraron atributos")
        )

        data = bytes([0x32])
        session_data = {"user_id": 999}

        task = TaskRequestAttributes(
            data,
            message_sender,
            request_attributes_handler=request_attributes_handler,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert
        request_attributes_handler.handle.assert_called_once()
        call_args = request_attributes_handler.handle.call_args[0][0]
        assert isinstance(call_args, RequestAttributesCommand)
        assert call_args.user_id == 999

    async def test_session_attributes_priority_over_repository(self) -> None:
        """Test que atributos de sesión tienen prioridad sobre repositorio."""
        # Setup
        message_sender = MagicMock()
        message_sender.send_attributes = AsyncMock()
        message_sender.connection.address = "127.0.0.1:1234"

        # Mock del handler
        request_attributes_handler = MagicMock()
        request_attributes_handler.handle = AsyncMock(
            return_value=CommandResult.ok(
                data={
                    "attributes": {
                        "strength": 18,
                        "agility": 15,
                        "intelligence": 12,
                        "charisma": 10,
                        "constitution": 14,
                    },
                    "from_session": True,
                }
            )
        )

        data = bytes([0x32])

        session_data = {
            "user_id": 1,
            "dice_attributes": {  # Estos deben tener prioridad
                "strength": 18,
                "agility": 15,
                "intelligence": 12,
                "charisma": 10,
                "constitution": 14,
            },
        }

        task = TaskRequestAttributes(
            data,
            message_sender,
            request_attributes_handler=request_attributes_handler,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert - debe usar los de sesión, no los del repositorio
        request_attributes_handler.handle.assert_called_once()
        call_args = request_attributes_handler.handle.call_args[0][0]
        assert isinstance(call_args, RequestAttributesCommand)
        assert call_args.dice_attributes == session_data["dice_attributes"]
        assert call_args.user_id is None  # No se usa user_id cuando hay dice_attributes
