"""Tests para MultiplayerBroadcastService."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.multiplayer_broadcast_service import MultiplayerBroadcastService


@pytest.fixture
def mock_map_manager() -> MagicMock:
    """Crea un mock de MapManager."""
    return MagicMock()


@pytest.fixture
def mock_player_repo() -> MagicMock:
    """Crea un mock de PlayerRepository."""
    return MagicMock()


@pytest.fixture
def mock_account_repo() -> MagicMock:
    """Crea un mock de AccountRepository."""
    repo = MagicMock()
    repo.get_account = AsyncMock()
    repo.get_account_by_user_id = AsyncMock()
    return repo


@pytest.fixture
def broadcast_service(
    mock_map_manager: MagicMock,
    mock_player_repo: MagicMock,
    mock_account_repo: MagicMock,
) -> MultiplayerBroadcastService:
    """Crea una instancia de MultiplayerBroadcastService con mocks."""
    return MultiplayerBroadcastService(mock_map_manager, mock_player_repo, mock_account_repo)


class TestIsInVisibleRange:
    """Tests para _is_in_visible_range."""

    def test_is_in_visible_range_within_range(self) -> None:
        """Test que dos posiciones dentro del rango devuelven True."""
        assert MultiplayerBroadcastService._is_in_visible_range(50, 50, 55, 55, 15) is True
        assert MultiplayerBroadcastService._is_in_visible_range(50, 50, 50, 50, 15) is True
        assert MultiplayerBroadcastService._is_in_visible_range(50, 50, 65, 50, 15) is True

    def test_is_in_visible_range_outside_range(self) -> None:
        """Test que dos posiciones fuera del rango devuelven False."""
        assert MultiplayerBroadcastService._is_in_visible_range(50, 50, 100, 100, 15) is False
        assert MultiplayerBroadcastService._is_in_visible_range(50, 50, 66, 50, 15) is False
        assert MultiplayerBroadcastService._is_in_visible_range(50, 50, 50, 66, 15) is False

    def test_is_in_visible_range_exact_boundary(self) -> None:
        """Test que el límite exacto del rango devuelve True."""
        assert MultiplayerBroadcastService._is_in_visible_range(50, 50, 65, 50, 15) is True
        assert MultiplayerBroadcastService._is_in_visible_range(50, 50, 50, 65, 15) is True
        assert MultiplayerBroadcastService._is_in_visible_range(50, 50, 35, 50, 15) is True


class TestNotifyPlayerSpawn:
    """Tests para notify_player_spawn."""

    @pytest.mark.asyncio
    async def test_notify_player_spawn_new_player(
        self,
        broadcast_service: MultiplayerBroadcastService,
        mock_map_manager: MagicMock,
        mock_player_repo: MagicMock,
        mock_account_repo: MagicMock,
    ) -> None:
        """Test spawn de un nuevo jugador."""
        # Setup
        message_sender = MagicMock()
        message_sender.send_character_create = AsyncMock()

        # Jugadores existentes en el mapa
        mock_map_manager.get_players_in_map.return_value = [2, 3]
        mock_map_manager.get_all_message_senders_in_map.return_value = [
            MagicMock(send_character_create=AsyncMock()),
            MagicMock(send_character_create=AsyncMock()),
        ]

        mock_player_repo.get_position = AsyncMock(
            side_effect=[
                {"x": 10, "y": 10, "map": 1, "heading": 1},
                {"x": 20, "y": 20, "map": 1, "heading": 2},
            ]
        )
        mock_account_repo.get_account_by_user_id = AsyncMock(
            side_effect=[
                {"char_race": 1, "char_head": 1, "username": "player2"},
                {"char_race": 2, "char_head": 2, "username": "player3"},
            ]
        )
        mock_account_repo.get_account = AsyncMock(return_value={"char_race": 1, "char_head": 1})

        # Execute
        await broadcast_service.notify_player_spawn(
            user_id=1,
            username="newplayer",
            position={"x": 50, "y": 50, "map": 1, "heading": 3},
            message_sender=message_sender,
        )

        # Assert
        mock_map_manager.add_player.assert_called_once_with(1, 1, message_sender, "newplayer")
        assert message_sender.send_character_create.call_count == 2  # Para jugadores existentes

    @pytest.mark.asyncio
    async def test_notify_player_spawn_empty_map(
        self,
        broadcast_service: MultiplayerBroadcastService,
        mock_map_manager: MagicMock,
        mock_account_repo: MagicMock,
    ) -> None:
        """Test spawn en mapa vacío."""
        # Setup
        message_sender = MagicMock()
        message_sender.send_character_create = AsyncMock()

        mock_map_manager.get_players_in_map.return_value = []
        mock_map_manager.get_all_message_senders_in_map.return_value = []
        mock_account_repo.get_account = AsyncMock(return_value={"char_race": 1, "char_head": 1})

        # Execute
        await broadcast_service.notify_player_spawn(
            user_id=1,
            username="newplayer",
            position={"x": 50, "y": 50, "map": 1, "heading": 3},
            message_sender=message_sender,
        )

        # Assert
        mock_map_manager.add_player.assert_called_once()
        # No debe enviar CHARACTER_CREATE a jugadores existentes (no hay)
        message_sender.send_character_create.assert_not_called()


class TestSendExistingPlayersToNewPlayer:
    """Tests para _send_existing_players_to_new_player."""

    @pytest.mark.asyncio
    async def test_send_existing_players_to_new_player_with_players(
        self,
        broadcast_service: MultiplayerBroadcastService,
        mock_map_manager: MagicMock,
        mock_player_repo: MagicMock,
        mock_account_repo: MagicMock,
    ) -> None:
        """Test envío de jugadores existentes al nuevo jugador."""
        # Setup
        message_sender = MagicMock()
        message_sender.send_character_create = AsyncMock()

        mock_map_manager.get_players_in_map.return_value = [2, 3]
        mock_player_repo.get_position = AsyncMock(
            side_effect=[
                {"x": 10, "y": 10, "map": 1, "heading": 1},
                {"x": 20, "y": 20, "map": 1, "heading": 2},
            ]
        )
        mock_account_repo.get_account_by_user_id = AsyncMock(
            side_effect=[
                {"char_race": 1, "char_head": 1, "username": "player2"},
                {"char_race": 2, "char_head": 2, "username": "player3"},
            ]
        )

        # Execute
        await broadcast_service._send_existing_players_to_new_player(1, message_sender)

        # Assert
        assert message_sender.send_character_create.call_count == 2

    @pytest.mark.asyncio
    async def test_send_existing_players_to_new_player_no_position(
        self,
        broadcast_service: MultiplayerBroadcastService,
        mock_map_manager: MagicMock,
        mock_player_repo: MagicMock,
    ) -> None:
        """Test cuando un jugador no tiene posición."""
        # Setup
        message_sender = MagicMock()
        message_sender.send_character_create = AsyncMock()

        mock_map_manager.get_players_in_map.return_value = [2]
        mock_player_repo.get_position = AsyncMock(return_value=None)  # Sin posición

        # Execute
        await broadcast_service._send_existing_players_to_new_player(1, message_sender)

        # Assert
        message_sender.send_character_create.assert_not_called()

    @pytest.mark.asyncio
    async def test_send_existing_players_to_new_player_no_account(
        self,
        broadcast_service: MultiplayerBroadcastService,
        mock_map_manager: MagicMock,
        mock_player_repo: MagicMock,
        mock_account_repo: MagicMock,
    ) -> None:
        """Test cuando un jugador no tiene cuenta."""
        # Setup
        message_sender = MagicMock()
        message_sender.send_character_create = AsyncMock()

        mock_map_manager.get_players_in_map.return_value = [2]
        mock_player_repo.get_position = AsyncMock(
            return_value={"x": 10, "y": 10, "map": 1, "heading": 1}
        )
        mock_account_repo.get_account_by_user_id = AsyncMock(return_value=None)  # Sin cuenta

        # Execute
        await broadcast_service._send_existing_players_to_new_player(1, message_sender)

        # Assert
        message_sender.send_character_create.assert_not_called()

    @pytest.mark.asyncio
    async def test_send_existing_players_to_new_player_body_zero(
        self,
        broadcast_service: MultiplayerBroadcastService,
        mock_map_manager: MagicMock,
        mock_player_repo: MagicMock,
        mock_account_repo: MagicMock,
    ) -> None:
        """Test cuando body es 0 (debe usar valor por defecto 1)."""
        # Setup
        message_sender = MagicMock()
        message_sender.send_character_create = AsyncMock()

        mock_map_manager.get_players_in_map.return_value = [2]
        mock_player_repo.get_position = AsyncMock(
            return_value={"x": 10, "y": 10, "map": 1, "heading": 1}
        )
        mock_account_repo.get_account_by_user_id = AsyncMock(
            return_value={"char_race": 0, "char_head": 1, "username": "player2"}
        )

        # Execute
        await broadcast_service._send_existing_players_to_new_player(1, message_sender)

        # Assert
        message_sender.send_character_create.assert_called_once()
        call_args = message_sender.send_character_create.call_args[1]
        assert call_args["body"] == 1  # Debe usar valor por defecto


class TestBroadcastNewPlayerToOthers:
    """Tests para _broadcast_new_player_to_others."""

    @pytest.mark.asyncio
    async def test_broadcast_new_player_to_others_with_players(
        self,
        broadcast_service: MultiplayerBroadcastService,
        mock_map_manager: MagicMock,
        mock_account_repo: MagicMock,
    ) -> None:
        """Test broadcast de nuevo jugador a otros."""
        # Setup
        sender1 = MagicMock(send_character_create=AsyncMock())
        sender2 = MagicMock(send_character_create=AsyncMock())

        mock_map_manager.get_all_message_senders_in_map.return_value = [sender1, sender2]
        mock_account_repo.get_account = AsyncMock(return_value={"char_race": 1, "char_head": 1})

        # Execute
        notified = await broadcast_service._broadcast_new_player_to_others(
            user_id=1,
            username="newplayer",
            position={"x": 50, "y": 50, "map": 1, "heading": 3},
            map_id=1,
        )

        # Assert
        assert notified == 2
        assert sender1.send_character_create.call_count == 1
        assert sender2.send_character_create.call_count == 1

    @pytest.mark.asyncio
    async def test_broadcast_new_player_to_others_no_account_repo(
        self,
        broadcast_service: MultiplayerBroadcastService,
        mock_map_manager: MagicMock,
    ) -> None:
        """Test broadcast sin account_repo (usa valores por defecto)."""
        # Setup
        broadcast_service.account_repo = None
        sender = MagicMock(send_character_create=AsyncMock())

        mock_map_manager.get_all_message_senders_in_map.return_value = [sender]

        # Execute
        notified = await broadcast_service._broadcast_new_player_to_others(
            user_id=1,
            username="newplayer",
            position={"x": 50, "y": 50, "map": 1, "heading": 3},
            map_id=1,
        )

        # Assert
        assert notified == 1
        sender.send_character_create.assert_called_once()
        call_args = sender.send_character_create.call_args[1]
        assert call_args["body"] == 1  # Valor por defecto
        assert call_args["head"] == 1  # Valor por defecto


class TestBroadcastCharacterMove:
    """Tests para broadcast_character_move."""

    @pytest.mark.asyncio
    async def test_broadcast_character_move_with_heading_change(
        self,
        broadcast_service: MultiplayerBroadcastService,
        mock_map_manager: MagicMock,
        mock_player_repo: MagicMock,
        mock_account_repo: MagicMock,
    ) -> None:
        """Test broadcast de movimiento con cambio de heading."""
        # Setup
        sender = MagicMock()
        sender.send_character_move = AsyncMock()
        sender.send_character_change = AsyncMock()

        mock_map_manager.get_players_in_map.return_value = [1]
        mock_map_manager.get_message_sender.return_value = sender
        mock_map_manager.get_username.return_value = "testuser"
        mock_player_repo.get_position = AsyncMock(return_value={"x": 50, "y": 50, "map": 1})
        mock_account_repo.get_account = AsyncMock(return_value={"char_race": 1, "char_head": 1})

        # Execute
        notified = await broadcast_service.broadcast_character_move(
            map_id=1,
            char_index=10001,
            new_x=51,
            new_y=50,
            new_heading=2,
            old_x=50,
            old_y=50,
            old_heading=1,  # Heading cambió
        )

        # Assert
        assert notified == 1
        sender.send_character_move.assert_called_once_with(10001, 51, 50)
        sender.send_character_change.assert_called_once()

    @pytest.mark.asyncio
    async def test_broadcast_character_move_no_heading_change(
        self,
        broadcast_service: MultiplayerBroadcastService,
        mock_map_manager: MagicMock,
        mock_player_repo: MagicMock,
        mock_account_repo: MagicMock,
    ) -> None:
        """Test broadcast de movimiento sin cambio de heading."""
        # Setup
        sender = MagicMock()
        sender.send_character_move = AsyncMock()
        sender.send_character_change = AsyncMock()

        mock_map_manager.get_players_in_map.return_value = [1]
        mock_map_manager.get_message_sender.return_value = sender
        mock_map_manager.get_username.return_value = "testuser"
        mock_player_repo.get_position = AsyncMock(return_value={"x": 50, "y": 50, "map": 1})
        mock_account_repo.get_account = AsyncMock(return_value={"char_race": 1, "char_head": 1})

        # Execute
        notified = await broadcast_service.broadcast_character_move(
            map_id=1,
            char_index=10001,
            new_x=51,
            new_y=50,
            new_heading=2,
            old_x=50,
            old_y=50,
            old_heading=2,  # Heading no cambió
        )

        # Assert
        assert notified == 1
        sender.send_character_move.assert_called_once()
        sender.send_character_change.assert_not_called()  # No debe enviar si heading no cambió

    @pytest.mark.asyncio
    async def test_broadcast_character_move_out_of_range(
        self,
        broadcast_service: MultiplayerBroadcastService,
        mock_map_manager: MagicMock,
        mock_player_repo: MagicMock,
    ) -> None:
        """Test broadcast de movimiento fuera de rango visible."""
        # Setup
        mock_map_manager.get_players_in_map.return_value = [1]
        mock_player_repo.get_position = AsyncMock(
            return_value={"x": 100, "y": 100, "map": 1}  # Fuera de rango (15 tiles)
        )

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
        assert notified == 0  # No debe notificar jugadores fuera de rango


class TestGetCharacterAppearance:
    """Tests para _get_character_appearance."""

    @pytest.mark.asyncio
    async def test_get_character_appearance_npc(
        self,
        broadcast_service: MultiplayerBroadcastService,
        mock_map_manager: MagicMock,
    ) -> None:
        """Test obtener apariencia de NPC."""
        # Setup
        mock_npc = MagicMock()
        mock_npc.body_id = 100
        mock_npc.head_id = 10

        mock_map_manager.get_npc_by_char_index.return_value = mock_npc

        # Execute
        body, head = await broadcast_service._get_character_appearance(10001, 1)

        # Assert
        assert body == 100
        assert head == 10

    @pytest.mark.asyncio
    async def test_get_character_appearance_npc_not_found(
        self,
        broadcast_service: MultiplayerBroadcastService,
        mock_map_manager: MagicMock,
    ) -> None:
        """Test obtener apariencia de NPC no encontrado."""
        # Setup
        mock_map_manager.get_npc_by_char_index.return_value = None

        # Execute
        body, head = await broadcast_service._get_character_appearance(10001, 1)

        # Assert
        assert body == 1  # Valor por defecto
        assert head == 0  # Valor por defecto

    @pytest.mark.asyncio
    async def test_get_character_appearance_player(
        self,
        broadcast_service: MultiplayerBroadcastService,
        mock_map_manager: MagicMock,
        mock_account_repo: MagicMock,
    ) -> None:
        """Test obtener apariencia de jugador."""
        # Setup
        mock_map_manager.get_username.return_value = "testuser"
        mock_account_repo.get_account = AsyncMock(return_value={"char_race": 2, "char_head": 5})

        # Execute
        body, head = await broadcast_service._get_character_appearance(1, 1)

        # Assert
        assert body == 2
        assert head == 5

    @pytest.mark.asyncio
    async def test_get_character_appearance_player_body_zero(
        self,
        broadcast_service: MultiplayerBroadcastService,
        mock_map_manager: MagicMock,
        mock_account_repo: MagicMock,
    ) -> None:
        """Test obtener apariencia de jugador con body=0 (debe usar 1)."""
        # Setup
        mock_map_manager.get_username.return_value = "testuser"
        mock_account_repo.get_account = AsyncMock(return_value={"char_race": 0, "char_head": 5})

        # Execute
        body, head = await broadcast_service._get_character_appearance(1, 1)

        # Assert
        assert body == 1  # Debe usar valor por defecto
        assert head == 5


class TestBroadcastCharacterCreate:
    """Tests para broadcast_character_create."""

    @pytest.mark.asyncio
    async def test_broadcast_character_create_with_players(
        self,
        broadcast_service: MultiplayerBroadcastService,
        mock_map_manager: MagicMock,
    ) -> None:
        """Test broadcast de CHARACTER_CREATE con jugadores."""
        # Setup
        sender1 = MagicMock(send_character_create=AsyncMock())
        sender2 = MagicMock(send_character_create=AsyncMock())

        mock_map_manager.get_all_message_senders_in_map.return_value = [sender1, sender2]

        # Execute
        notified = await broadcast_service.broadcast_character_create(
            map_id=1,
            char_index=10001,
            body=100,
            head=10,
            heading=2,
            x=50,
            y=50,
            name="TestNPC",
        )

        # Assert
        assert notified == 2
        assert sender1.send_character_create.call_count == 1
        assert sender2.send_character_create.call_count == 1

    @pytest.mark.asyncio
    async def test_broadcast_character_create_no_players(
        self,
        broadcast_service: MultiplayerBroadcastService,
        mock_map_manager: MagicMock,
    ) -> None:
        """Test broadcast de CHARACTER_CREATE sin jugadores."""
        # Setup
        mock_map_manager.get_all_message_senders_in_map.return_value = []

        # Execute
        notified = await broadcast_service.broadcast_character_create(
            map_id=1,
            char_index=10001,
            body=100,
            head=10,
            heading=2,
            x=50,
            y=50,
            name="TestNPC",
        )

        # Assert
        assert notified == 0


class TestBroadcastCharacterRemove:
    """Tests para broadcast_character_remove."""

    @pytest.mark.asyncio
    async def test_broadcast_character_remove_with_players(
        self,
        broadcast_service: MultiplayerBroadcastService,
        mock_map_manager: MagicMock,
    ) -> None:
        """Test broadcast de CHARACTER_REMOVE con jugadores."""
        # Setup
        sender1 = MagicMock(send_character_remove=AsyncMock())
        sender2 = MagicMock(send_character_remove=AsyncMock())

        mock_map_manager.get_all_message_senders_in_map.return_value = [sender1, sender2]

        # Execute
        notified = await broadcast_service.broadcast_character_remove(1, 10001)

        # Assert
        assert notified == 2
        assert sender1.send_character_remove.call_count == 1
        assert sender2.send_character_remove.call_count == 1

    @pytest.mark.asyncio
    async def test_broadcast_character_remove_no_players(
        self,
        broadcast_service: MultiplayerBroadcastService,
        mock_map_manager: MagicMock,
    ) -> None:
        """Test broadcast de CHARACTER_REMOVE sin jugadores."""
        # Setup
        mock_map_manager.get_all_message_senders_in_map.return_value = []

        # Execute
        notified = await broadcast_service.broadcast_character_remove(1, 10001)

        # Assert
        assert notified == 0


class TestBroadcastBlockPosition:
    """Tests para broadcast_block_position."""

    @pytest.mark.asyncio
    async def test_broadcast_block_position_blocked(
        self,
        broadcast_service: MultiplayerBroadcastService,
        mock_map_manager: MagicMock,
    ) -> None:
        """Test broadcast de BLOCK_POSITION bloqueado."""
        # Setup
        sender = MagicMock(send_block_position=AsyncMock())
        mock_map_manager.get_all_message_senders_in_map.return_value = [sender]

        # Execute
        notified = await broadcast_service.broadcast_block_position(1, 10, 20, True)  # noqa: FBT003

        # Assert
        assert notified == 1
        sender.send_block_position.assert_called_once_with(10, 20, True)  # noqa: FBT003

    @pytest.mark.asyncio
    async def test_broadcast_block_position_unblocked(
        self,
        broadcast_service: MultiplayerBroadcastService,
        mock_map_manager: MagicMock,
    ) -> None:
        """Test broadcast de BLOCK_POSITION desbloqueado."""
        # Setup
        sender = MagicMock(send_block_position=AsyncMock())
        mock_map_manager.get_all_message_senders_in_map.return_value = [sender]

        # Execute
        notified = await broadcast_service.broadcast_block_position(1, 10, 20, False)  # noqa: FBT003

        # Assert
        assert notified == 1
        sender.send_block_position.assert_called_once_with(10, 20, False)  # noqa: FBT003


class TestBroadcastObjectCreate:
    """Tests para broadcast_object_create."""

    @pytest.mark.asyncio
    async def test_broadcast_object_create_with_players(
        self,
        broadcast_service: MultiplayerBroadcastService,
        mock_map_manager: MagicMock,
    ) -> None:
        """Test broadcast de OBJECT_CREATE con jugadores."""
        # Setup
        sender = MagicMock(send_object_create=AsyncMock())
        mock_map_manager.get_all_message_senders_in_map.return_value = [sender]

        # Execute
        notified = await broadcast_service.broadcast_object_create(1, 10, 20, 1001)

        # Assert
        assert notified == 1
        sender.send_object_create.assert_called_once_with(10, 20, 1001)

    @pytest.mark.asyncio
    async def test_broadcast_object_create_no_players(
        self,
        broadcast_service: MultiplayerBroadcastService,
        mock_map_manager: MagicMock,
    ) -> None:
        """Test broadcast de OBJECT_CREATE sin jugadores."""
        # Setup
        mock_map_manager.get_all_message_senders_in_map.return_value = []

        # Execute
        notified = await broadcast_service.broadcast_object_create(1, 10, 20, 1001)

        # Assert
        assert notified == 0


class TestBroadcastObjectDelete:
    """Tests para broadcast_object_delete."""

    @pytest.mark.asyncio
    async def test_broadcast_object_delete_with_players(
        self,
        broadcast_service: MultiplayerBroadcastService,
        mock_map_manager: MagicMock,
    ) -> None:
        """Test broadcast de OBJECT_DELETE con jugadores."""
        # Setup
        sender = MagicMock(send_object_delete=AsyncMock())
        mock_map_manager.get_all_message_senders_in_map.return_value = [sender]

        # Execute
        await broadcast_service.broadcast_object_delete(1, 10, 20)

        # Assert
        sender.send_object_delete.assert_called_once_with(10, 20)

    @pytest.mark.asyncio
    async def test_broadcast_object_delete_no_map_manager(
        self,
        broadcast_service: MultiplayerBroadcastService,
    ) -> None:
        """Test broadcast de OBJECT_DELETE sin map_manager."""
        # Setup
        broadcast_service.map_manager = None

        # Execute - No debe crashear
        await broadcast_service.broadcast_object_delete(1, 10, 20)


class TestBroadcastCreateFx:
    """Tests para broadcast_create_fx."""

    @pytest.mark.asyncio
    async def test_broadcast_create_fx_with_players(
        self,
        broadcast_service: MultiplayerBroadcastService,
        mock_map_manager: MagicMock,
    ) -> None:
        """Test broadcast de CREATE_FX con jugadores."""
        # Setup
        sender = MagicMock(send_create_fx=AsyncMock())
        mock_map_manager.get_all_message_senders_in_map.return_value = [sender]

        # Execute
        await broadcast_service.broadcast_create_fx(1, 10001, 5, 1)

        # Assert
        sender.send_create_fx.assert_called_once_with(10001, 5, 1)

    @pytest.mark.asyncio
    async def test_broadcast_create_fx_no_map_manager(
        self,
        broadcast_service: MultiplayerBroadcastService,
    ) -> None:
        """Test broadcast de CREATE_FX sin map_manager."""
        # Setup
        broadcast_service.map_manager = None

        # Execute - No debe crashear
        await broadcast_service.broadcast_create_fx(1, 10001, 5, 1)
