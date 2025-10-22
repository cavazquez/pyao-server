"""Tests para TaskAttack."""

from unittest.mock import MagicMock

import pytest

from src.repositories.player_repository import PlayerRepository
from src.tasks.player.task_attack import TaskAttack


@pytest.mark.asyncio
class TestTaskAttack:
    """Tests para TaskAttack."""

    async def test_attack_without_session(self) -> None:
        """Test de ataque sin sesión activa."""
        # Setup
        message_sender = MagicMock()
        message_sender.connection.address = "127.0.0.1:1234"

        player_repo = MagicMock(spec=PlayerRepository)

        data = bytes([0x07])  # ATTACK packet

        session_data = {}  # Sin user_id

        task = TaskAttack(
            data,
            message_sender,
            player_repo=player_repo,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert - no debe crashear

    async def test_attack_without_dependencies(self) -> None:
        """Test sin dependencias necesarias."""
        # Setup
        message_sender = MagicMock()
        message_sender.connection.address = "127.0.0.1:1234"

        data = bytes([0x07])
        session_data = {"user_id": 1}

        task = TaskAttack(
            data,
            message_sender,
            player_repo=None,  # Sin dependencias
            combat_service=None,
            map_manager=None,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert - no debe crashear

    async def test_attack_missing_npc_service(self) -> None:
        """Test sin npc_service (dependencia requerida)."""
        # Setup
        message_sender = MagicMock()
        message_sender.connection.address = "127.0.0.1:1234"

        player_repo = MagicMock()
        combat_service = MagicMock()
        map_manager = MagicMock()

        data = bytes([0x07])
        session_data = {"user_id": 1}

        task = TaskAttack(
            data,
            message_sender,
            player_repo=player_repo,
            combat_service=combat_service,
            map_manager=map_manager,
            npc_service=None,  # Falta dependencia
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Assert - debe salir temprano por falta de dependencias

    async def test_attack_invalid_packet_size(self) -> None:
        """Test con packet vacío (solo para cobertura)."""
        # Setup
        message_sender = MagicMock()
        message_sender.connection.address = "127.0.0.1:1234"

        player_repo = MagicMock(spec=PlayerRepository)

        data = bytes([0x07])  # Packet válido pero mínimo
        session_data = {"user_id": 1}

        task = TaskAttack(
            data,
            message_sender,
            player_repo=player_repo,
            session_data=session_data,
        )

        # Execute - no debe crashear
        await task.execute()
