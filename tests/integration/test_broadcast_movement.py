"""Tests para broadcast de movimiento de NPCs."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.multiplayer_broadcast_service import MultiplayerBroadcastService


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

        map_manager.get_players_in_map.return_value = [1, 2]
        map_manager.get_message_sender.side_effect = (
            lambda uid, _mid: sender1 if uid == 1 else sender2
        )
        map_manager.get_username.return_value = "testuser"
        player_repo.get_position = AsyncMock(return_value={"x": 50, "y": 50, "map": 1})
        account_repo.get_account = AsyncMock(return_value={"char_race": "1", "char_head": "1"})

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

        map_manager.get_players_in_map.return_value = [1]
        map_manager.get_message_sender.return_value = sender
        map_manager.get_username.return_value = "testuser"
        player_repo.get_position = AsyncMock(return_value={"x": 72, "y": 71, "map": 1})
        account_repo.get_account = AsyncMock(return_value={"char_race": "1", "char_head": "1"})

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


@pytest.mark.asyncio
async def test_broadcast_character_move_filters_by_range():
    """Test que broadcast filtra jugadores fuera de rango visible."""
    # Setup
    map_manager = MagicMock()
    player_repo = MagicMock()
    account_repo = MagicMock()

    sender_near = MagicMock()
    sender_near.send_character_move = AsyncMock()
    sender_near.send_character_change = AsyncMock()

    sender_far = MagicMock()
    sender_far.send_character_move = AsyncMock()
    sender_far.send_character_change = AsyncMock()

    # Jugador 1 está cerca (dentro de rango 15)
    # Jugador 2 está lejos (fuera de rango 15)
    map_manager.get_players_in_map.return_value = [1, 2]

    def get_sender(uid, _mid):
        return sender_near if uid == 1 else sender_far

    map_manager.get_message_sender.side_effect = get_sender
    map_manager.get_username.return_value = "testuser"

    # Posiciones: char_index en (50, 50)
    # Jugador 1 en (55, 55) - distancia Chebyshev = 5 (dentro de rango 15)
    # Jugador 2 en (100, 100) - distancia Chebyshev = 50 (fuera de rango 15)
    def get_position(uid):
        if uid == 1:
            return {"x": 55, "y": 55, "map": 1}
        return {"x": 100, "y": 100, "map": 1}

    player_repo.get_position = AsyncMock(side_effect=get_position)
    account_repo.get_account = AsyncMock(return_value={"char_race": "1", "char_head": "1"})

    broadcast_service = MultiplayerBroadcastService(map_manager, player_repo, account_repo)

    # Execute
    notified = await broadcast_service.broadcast_character_move(
        map_id=1,
        char_index=10001,
        new_x=50,
        new_y=50,
        new_heading=2,
        old_x=49,
        old_y=50,
    )

    # Assert
    assert notified == 1  # Solo el jugador cercano fue notificado
    sender_near.send_character_move.assert_called_once_with(10001, 50, 50)
    sender_far.send_character_move.assert_not_called()  # Jugador lejano NO fue notificado
