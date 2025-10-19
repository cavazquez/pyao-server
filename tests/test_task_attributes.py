"""Tests para TaskRequestAttributes."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.player_repository import PlayerRepository
from src.task_attributes import TaskRequestAttributes


@pytest.mark.asyncio
class TestTaskRequestAttributes:
    """Tests para TaskRequestAttributes."""

    async def test_send_attributes_from_session(self) -> None:
        """Test de envío de atributos desde sesión (creación de personaje)."""
        # Setup
        message_sender = MagicMock()
        message_sender.send_attributes = AsyncMock()
        message_sender.connection.address = "127.0.0.1:1234"

        player_repo = MagicMock(spec=PlayerRepository)

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
            data, message_sender, player_repo=player_repo, session_data=session_data
        )

        # Execute
        await task.execute()

        # Assert
        message_sender.send_attributes.assert_called_once_with(
            strength=18, agility=15, intelligence=12, charisma=10, constitution=14
        )
        # No debe consultar el repositorio
        player_repo.get_attributes.assert_not_called()

    async def test_send_attributes_from_repository(self) -> None:
        """Test de envío de atributos desde repositorio."""
        # Setup
        message_sender = MagicMock()
        message_sender.send_attributes = AsyncMock()
        message_sender.connection.address = "127.0.0.1:1234"

        player_repo = MagicMock(spec=PlayerRepository)
        player_repo.get_attributes = AsyncMock(
            return_value={
                "strength": 20,
                "agility": 16,
                "intelligence": 14,
                "charisma": 12,
                "constitution": 18,
            }
        )

        data = bytes([0x32])

        session_data = {"user_id": 1}

        task = TaskRequestAttributes(
            data, message_sender, player_repo=player_repo, session_data=session_data
        )

        # Execute
        await task.execute()

        # Assert
        player_repo.get_attributes.assert_called_once_with(1)
        message_sender.send_attributes.assert_called_once_with(
            strength=20, agility=16, intelligence=14, charisma=12, constitution=18
        )

    async def test_send_attributes_without_repository(self) -> None:
        """Test sin repositorio disponible."""
        # Setup
        message_sender = MagicMock()
        message_sender.send_attributes = AsyncMock()
        message_sender.connection.address = "127.0.0.1:1234"

        data = bytes([0x32])
        session_data = {"user_id": 1}

        task = TaskRequestAttributes(
            data, message_sender, player_repo=None, session_data=session_data
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

        player_repo = MagicMock(spec=PlayerRepository)

        data = bytes([0x32])
        session_data = {}  # Sin user_id

        task = TaskRequestAttributes(
            data, message_sender, player_repo=player_repo, session_data=session_data
        )

        # Execute
        await task.execute()

        # Assert - debe enviar ceros
        message_sender.send_attributes.assert_called_once_with(0, 0, 0, 0, 0)
        player_repo.get_attributes.assert_not_called()

    async def test_send_attributes_with_dict_user_id(self) -> None:
        """Test con user_id como dict (caso inválido)."""
        # Setup
        message_sender = MagicMock()
        message_sender.send_attributes = AsyncMock()
        message_sender.connection.address = "127.0.0.1:1234"

        player_repo = MagicMock(spec=PlayerRepository)

        data = bytes([0x32])
        session_data = {"user_id": {"invalid": "data"}}  # user_id inválido

        task = TaskRequestAttributes(
            data, message_sender, player_repo=player_repo, session_data=session_data
        )

        # Execute
        await task.execute()

        # Assert - debe enviar ceros
        message_sender.send_attributes.assert_called_once_with(0, 0, 0, 0, 0)
        player_repo.get_attributes.assert_not_called()

    async def test_send_attributes_not_found_in_repository(self) -> None:
        """Test cuando no se encuentran atributos en el repositorio."""
        # Setup
        message_sender = MagicMock()
        message_sender.send_attributes = AsyncMock()
        message_sender.connection.address = "127.0.0.1:1234"

        player_repo = MagicMock(spec=PlayerRepository)
        player_repo.get_attributes = AsyncMock(return_value=None)  # No encontrado

        data = bytes([0x32])
        session_data = {"user_id": 999}

        task = TaskRequestAttributes(
            data, message_sender, player_repo=player_repo, session_data=session_data
        )

        # Execute
        await task.execute()

        # Assert
        player_repo.get_attributes.assert_called_once_with(999)
        message_sender.send_attributes.assert_called_once_with(0, 0, 0, 0, 0)

    async def test_session_attributes_priority_over_repository(self) -> None:
        """Test que atributos de sesión tienen prioridad sobre repositorio."""
        # Setup
        message_sender = MagicMock()
        message_sender.send_attributes = AsyncMock()
        message_sender.connection.address = "127.0.0.1:1234"

        player_repo = MagicMock(spec=PlayerRepository)
        player_repo.get_attributes = AsyncMock(
            return_value={
                "strength": 10,
                "agility": 10,
                "intelligence": 10,
                "charisma": 10,
                "constitution": 10,
            }
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
            data, message_sender, player_repo=player_repo, session_data=session_data
        )

        # Execute
        await task.execute()

        # Assert - debe usar los de sesión, no los del repositorio
        message_sender.send_attributes.assert_called_once_with(
            strength=18, agility=15, intelligence=12, charisma=10, constitution=14
        )
        player_repo.get_attributes.assert_not_called()
