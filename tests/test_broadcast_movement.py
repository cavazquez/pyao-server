"""Tests para broadcast de movimiento de NPCs."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.multiplayer_broadcast_service import MultiplayerBroadcastService


class TestBroadcastMovement:
    """Tests para broadcast de movimiento."""

    @pytest.mark.asyncio
    async def test_broadcast_character_move_to_players(self) -> None:
        """Test broadcast de CHARACTER_MOVE a jugadores en el mapa."""
        # Setup
        map_manager = MagicMock()
        player_repo = MagicMock()
        account_repo = MagicMock()

        # Crear message_senders mock
        sender1 = MagicMock()
        sender1.send_character_move = AsyncMock()
        sender1.send_character_change = AsyncMock()
        sender2 = MagicMock()
        sender2.send_character_move = AsyncMock()
        sender2.send_character_change = AsyncMock()

        map_manager.get_all_message_senders_in_map.return_value = [sender1, sender2]

        broadcast_service = MultiplayerBroadcastService(map_manager, player_repo, account_repo)

        # Execute
        notified = await broadcast_service.broadcast_character_move(
            map_id=1,
            char_index=10001,
            new_x=51,
            new_y=50,
            new_heading=2,
            old_x=50,
            old_y=50,
        )

        # Assert
        assert notified == 2
        sender1.send_character_move.assert_called_once_with(10001, 51, 50)
        sender2.send_character_move.assert_called_once_with(10001, 51, 50)
        # CHARACTER_CHANGE también se envía porque old_heading es None
        sender1.send_character_change.assert_called_once()
        sender2.send_character_change.assert_called_once()

    @pytest.mark.asyncio
    async def test_broadcast_character_move_no_players(self) -> None:
        """Test broadcast cuando no hay jugadores en el mapa."""
        # Setup
        map_manager = MagicMock()
        player_repo = MagicMock()
        account_repo = MagicMock()

        map_manager.get_all_message_senders_in_map.return_value = []

        broadcast_service = MultiplayerBroadcastService(map_manager, player_repo, account_repo)

        # Execute
        notified = await broadcast_service.broadcast_character_move(
            map_id=1,
            char_index=10001,
            new_x=51,
            new_y=50,
            new_heading=2,
            old_x=50,
            old_y=50,
        )

        # Assert
        assert notified == 0

    @pytest.mark.asyncio
    async def test_broadcast_character_move_single_player(self) -> None:
        """Test broadcast a un solo jugador."""
        # Setup
        map_manager = MagicMock()
        player_repo = MagicMock()
        account_repo = MagicMock()

        sender = MagicMock()
        sender.send_character_move = AsyncMock()
        sender.send_character_change = AsyncMock()

        map_manager.get_all_message_senders_in_map.return_value = [sender]

        broadcast_service = MultiplayerBroadcastService(map_manager, player_repo, account_repo)

        # Execute
        notified = await broadcast_service.broadcast_character_move(
            map_id=1,
            char_index=10005,
            new_x=72,
            new_y=71,
            new_heading=3,
            old_x=72,
            old_y=70,
        )

        # Assert
        assert notified == 1
        sender.send_character_move.assert_called_once_with(10005, 72, 71)
        sender.send_character_change.assert_called_once()
