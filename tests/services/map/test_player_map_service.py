"""Tests para PlayerMapService."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.models.npc import NPC
from src.services.map.player_map_service import PlayerMapService, PlayerVisualData


@pytest.fixture
def mock_player_repo():
    """Mock de PlayerRepository."""
    repo = AsyncMock()
    repo.get_position.return_value = {"x": 50, "y": 50, "map": 1, "heading": 3}
    repo.set_position = AsyncMock()
    return repo


@pytest.fixture
def mock_account_repo():
    """Mock de AccountRepository."""
    repo = AsyncMock()
    repo.get_account_by_user_id.return_value = {
        "username": "TestPlayer",
        "char_race": 2,
        "char_head": 3,
    }
    return repo


@pytest.fixture
def mock_map_manager():
    """Mock de MapManager."""
    manager = MagicMock()
    manager.get_players_in_map.return_value = []
    manager.get_npcs_in_map.return_value = []
    manager._ground_items = {}
    manager.add_player = MagicMock()
    manager.remove_player = MagicMock()
    manager.update_player_tile = MagicMock()
    return manager


@pytest.fixture
def mock_broadcast_service():
    """Mock de MultiplayerBroadcastService."""
    service = AsyncMock()
    service.broadcast_character_create = AsyncMock()
    service.broadcast_character_remove = AsyncMock()
    return service


@pytest.fixture
def mock_message_sender():
    """Mock de MessageSender."""
    sender = AsyncMock()
    sender.send_character_create = AsyncMock()
    sender.send_change_map = AsyncMock()
    sender.send_pos_update = AsyncMock()
    sender.send_object_create = AsyncMock()
    sender.send_block_position = AsyncMock()
    return sender


@pytest.fixture
def player_map_service(
    mock_player_repo, mock_account_repo, mock_map_manager, mock_broadcast_service
):
    """Fixture de PlayerMapService."""
    return PlayerMapService(
        player_repo=mock_player_repo,
        account_repo=mock_account_repo,
        map_manager=mock_map_manager,
        broadcast_service=mock_broadcast_service,
    )


class TestPlayerVisualData:
    """Tests para PlayerVisualData dataclass."""

    def test_player_visual_data_creation(self):
        """Test creación de PlayerVisualData."""
        data = PlayerVisualData(user_id=1, username="TestPlayer", char_body=2, char_head=3)

        assert data.user_id == 1
        assert data.username == "TestPlayer"
        assert data.char_body == 2
        assert data.char_head == 3


class TestPlayerMapService:
    """Tests para PlayerMapService."""

    def test_init(self, player_map_service):
        """Test inicialización del servicio."""
        assert player_map_service is not None
        assert player_map_service.player_repo is not None
        assert player_map_service.account_repo is not None
        assert player_map_service.map_manager is not None
        assert player_map_service.broadcast_service is not None

    @pytest.mark.asyncio
    async def test_get_player_visual_data(self, player_map_service):
        """Test obtener datos visuales del jugador."""
        visual_data = await player_map_service._get_player_visual_data(1)

        assert visual_data.user_id == 1
        assert visual_data.username == "TestPlayer"
        assert visual_data.char_body == 2
        assert visual_data.char_head == 3

    @pytest.mark.asyncio
    async def test_get_player_visual_data_no_account(self, player_map_service):
        """Test obtener datos visuales cuando no hay cuenta."""
        player_map_service.account_repo.get_account_by_user_id.return_value = None

        visual_data = await player_map_service._get_player_visual_data(1)

        # Debe usar valores por defecto
        assert visual_data.user_id == 1
        assert visual_data.username == "Player1"
        assert visual_data.char_body == 1
        assert visual_data.char_head == 1

    @pytest.mark.asyncio
    async def test_get_player_visual_data_body_zero(self, player_map_service):
        """Test que body 0 se reemplaza por 1."""
        player_map_service.account_repo.get_account_by_user_id.return_value = {
            "username": "TestPlayer",
            "char_race": 0,  # Body inválido
            "char_head": 3,
        }

        visual_data = await player_map_service._get_player_visual_data(1)

        # Body 0 debe convertirse en 1
        assert visual_data.char_body == 1

    @pytest.mark.asyncio
    async def test_send_players_in_map_empty(self, player_map_service, mock_message_sender):
        """Test enviar jugadores cuando el mapa está vacío."""
        count = await player_map_service._send_players_in_map(1, mock_message_sender)

        assert count == 0
        mock_message_sender.send_character_create.assert_not_called()

    @pytest.mark.asyncio
    async def test_send_players_in_map_with_players(self, player_map_service, mock_message_sender):
        """Test enviar jugadores cuando hay otros jugadores."""
        # Simular 2 jugadores en el mapa
        player_map_service.map_manager.get_players_in_map.return_value = [2, 3]

        count = await player_map_service._send_players_in_map(1, mock_message_sender)

        assert count == 2
        assert mock_message_sender.send_character_create.call_count == 2

    @pytest.mark.asyncio
    async def test_send_players_in_map_exclude_self(self, player_map_service, mock_message_sender):
        """Test que se excluye al jugador especificado."""
        # Simular 3 jugadores en el mapa (incluyendo el propio)
        player_map_service.map_manager.get_players_in_map.return_value = [1, 2, 3]

        count = await player_map_service._send_players_in_map(
            1, mock_message_sender, exclude_user_id=1
        )

        # Solo debe enviar 2 (excluye el 1)
        assert count == 2

    @pytest.mark.asyncio
    async def test_send_npcs_in_map_empty(self, player_map_service, mock_message_sender):
        """Test enviar NPCs cuando no hay NPCs."""
        count = await player_map_service._send_npcs_in_map(1, mock_message_sender)

        assert count == 0
        mock_message_sender.send_character_create.assert_not_called()

    @pytest.mark.asyncio
    async def test_send_npcs_in_map_with_npcs(self, player_map_service, mock_message_sender):
        """Test enviar NPCs cuando hay NPCs en el mapa."""
        # Crear NPCs de prueba
        npc1 = NPC(
            npc_id=1,
            char_index=10001,
            instance_id="test-npc-1",
            map_id=1,
            x=30,
            y=30,
            heading=3,
            name="Goblin",
            description="Un goblin hostil",
            body_id=14,
            head_id=0,
            hp=100,
            max_hp=100,
            level=5,
            is_hostile=True,
            is_attackable=True,
        )
        npc2 = NPC(
            npc_id=7,
            char_index=10002,
            instance_id="test-npc-2",
            map_id=1,
            x=40,
            y=40,
            heading=2,
            name="Lobo",
            description="Un lobo salvaje",
            body_id=10,
            head_id=0,
            hp=80,
            max_hp=80,
            level=3,
            is_hostile=True,
            is_attackable=True,
        )

        player_map_service.map_manager.get_npcs_in_map.return_value = [npc1, npc2]

        count = await player_map_service._send_npcs_in_map(1, mock_message_sender)

        assert count == 2
        assert mock_message_sender.send_character_create.call_count == 2

    @pytest.mark.asyncio
    async def test_send_ground_items_in_map_empty(self, player_map_service, mock_message_sender):
        """Test enviar ground items cuando no hay items."""
        count = await player_map_service._send_ground_items_in_map(1, mock_message_sender)

        assert count == 0
        mock_message_sender.send_object_create.assert_not_called()

    @pytest.mark.asyncio
    async def test_send_ground_items_in_map_with_items(
        self, player_map_service, mock_message_sender
    ):
        """Test enviar ground items cuando hay items en el suelo."""
        # Simular items en el suelo
        player_map_service.map_manager._ground_items = {
            (1, 50, 50): [{"grh_index": 100}],
            (1, 51, 51): [{"grh_index": 101}],
        }

        count = await player_map_service._send_ground_items_in_map(1, mock_message_sender)

        assert count == 2
        assert mock_message_sender.send_object_create.call_count == 2

    @pytest.mark.asyncio
    async def test_unblock_exit_tiles_without_exits(self, player_map_service, mock_message_sender):
        """No debe desbloquear tiles ni enviar BLOCK_POSITION si no hay exit tiles."""
        # El mock_map_manager por defecto no tiene _exit_tiles definido
        result = await player_map_service._unblock_exit_tiles(1, mock_message_sender)

        assert result == 0
        mock_message_sender.send_block_position.assert_not_called()

    @pytest.mark.asyncio
    async def test_unblock_exit_tiles_with_exits_filters_by_map(
        self, player_map_service, mock_message_sender
    ):
        """Debe enviar BLOCK_POSITION(false) solo para exit tiles del mapa indicado."""
        # Simular dos exit tiles, uno en el mapa 1 y otro en el mapa 2
        player_map_service.map_manager._exit_tiles = {
            (1, 10, 20): {"to_map": 2, "to_x": 50, "to_y": 99},
            (2, 30, 40): {"to_map": 3, "to_x": 99, "to_y": 50},
        }

        result = await player_map_service._unblock_exit_tiles(1, mock_message_sender)

        # Solo debe desbloquear el exit del mapa 1
        assert result == 1
        mock_message_sender.send_block_position.assert_awaited_once_with(10, 20, blocked=False)

    @pytest.mark.asyncio
    async def test_spawn_in_map(self, player_map_service, mock_message_sender):
        """Test spawn de jugador en mapa (login inicial)."""
        await player_map_service.spawn_in_map(
            user_id=1,
            map_id=1,
            x=50,
            y=50,
            heading=3,
            message_sender=mock_message_sender,
        )

        # Debe agregar jugador al mapa
        player_map_service.map_manager.add_player.assert_called_once()

        # Debe marcar el tile ocupado en el índice espacial
        player_map_service.map_manager.update_player_tile.assert_called_once_with(
            1, 1, 50, 50, 50, 50
        )

        # Debe enviar CHARACTER_CREATE del propio jugador
        assert mock_message_sender.send_character_create.call_count >= 1

        # Debe hacer broadcast
        player_map_service.broadcast_service.broadcast_character_create.assert_called_once()

    @pytest.mark.asyncio
    async def test_transition_to_map(self, player_map_service, mock_message_sender):
        """Test transición de jugador entre mapas."""
        await player_map_service.transition_to_map(
            user_id=1,
            current_map=1,
            current_x=50,
            current_y=50,
            new_map=2,
            new_x=60,
            new_y=60,
            heading=3,
            message_sender=mock_message_sender,
        )

        # 1. Debe enviar CHANGE_MAP
        mock_message_sender.send_change_map.assert_called_once_with(2)

        # 3. Debe actualizar posición en Redis
        player_map_service.player_repo.set_position.assert_called_once_with(1, 60, 60, 2, 3)

        # 4. Debe enviar POS_UPDATE
        mock_message_sender.send_pos_update.assert_called_once_with(60, 60)

        # 5. Debe remover del mapa anterior
        player_map_service.map_manager.remove_player.assert_called_once_with(1, 1)

        # 6. Debe broadcast CHARACTER_REMOVE en mapa anterior
        player_map_service.broadcast_service.broadcast_character_remove.assert_called_once_with(
            1, 1
        )

        # 7. Debe agregar al nuevo mapa
        player_map_service.map_manager.add_player.assert_called_once()

        # 7b. Debe marcar el tile ocupado en el nuevo mapa
        player_map_service.map_manager.update_player_tile.assert_called_once_with(
            1, 2, 60, 60, 60, 60
        )

        # 8. Debe enviar CHARACTER_CREATE del propio jugador
        assert mock_message_sender.send_character_create.call_count >= 1

        # 12. Debe broadcast CHARACTER_CREATE en nuevo mapa
        player_map_service.broadcast_service.broadcast_character_create.assert_called_once()

    @pytest.mark.asyncio
    async def test_transition_to_map_sequence(self, player_map_service, mock_message_sender):
        """Test que la secuencia de transición es correcta."""
        await player_map_service.transition_to_map(
            user_id=1,
            current_map=1,
            current_x=50,
            current_y=50,
            new_map=2,
            new_x=60,
            new_y=60,
            heading=3,
            message_sender=mock_message_sender,
        )

        # Verificar que CHANGE_MAP se llama antes que set_position
        call_order = [call[0] for call in mock_message_sender.method_calls]

        # CHANGE_MAP debe ser el primero
        assert "send_change_map" in call_order
        change_map_index = call_order.index("send_change_map")

        # POS_UPDATE debe venir después
        assert "send_pos_update" in call_order
        pos_update_index = call_order.index("send_pos_update")
        assert pos_update_index > change_map_index

    @pytest.mark.asyncio
    async def test_spawn_in_map_with_other_players(self, player_map_service, mock_message_sender):
        """Test spawn cuando hay otros jugadores en el mapa."""
        # Simular otros jugadores
        player_map_service.map_manager.get_players_in_map.return_value = [2, 3]

        await player_map_service.spawn_in_map(
            user_id=1,
            map_id=1,
            x=50,
            y=50,
            heading=3,
            message_sender=mock_message_sender,
        )

        # Debe enviar CHARACTER_CREATE del propio jugador + otros 2
        assert mock_message_sender.send_character_create.call_count >= 3

    @pytest.mark.asyncio
    async def test_spawn_in_map_with_npcs(self, player_map_service, mock_message_sender):
        """Test spawn cuando hay NPCs en el mapa."""
        npc = NPC(
            npc_id=1,
            char_index=10001,
            instance_id="test-npc-1",
            map_id=1,
            x=30,
            y=30,
            heading=3,
            name="Goblin",
            description="Un goblin hostil",
            body_id=14,
            head_id=0,
            hp=100,
            max_hp=100,
            level=5,
            is_hostile=True,
            is_attackable=True,
        )
        player_map_service.map_manager.get_npcs_in_map.return_value = [npc]

        await player_map_service.spawn_in_map(
            user_id=1,
            map_id=1,
            x=50,
            y=50,
            heading=3,
            message_sender=mock_message_sender,
        )

        # Debe enviar CHARACTER_CREATE del jugador + NPC
        assert mock_message_sender.send_character_create.call_count >= 2

    @pytest.mark.asyncio
    async def test_transition_same_map(self, player_map_service, mock_message_sender):
        """Test transición dentro del mismo mapa."""
        await player_map_service.transition_to_map(
            user_id=1,
            current_map=1,
            current_x=50,
            current_y=50,
            new_map=1,  # Mismo mapa
            new_x=60,
            new_y=60,
            heading=3,
            message_sender=mock_message_sender,
        )

        # Debe enviar CHANGE_MAP incluso si es el mismo mapa
        mock_message_sender.send_change_map.assert_called_once_with(1)

        # Debe remover y agregar del mismo mapa
        player_map_service.map_manager.remove_player.assert_called_once_with(1, 1)
        player_map_service.map_manager.add_player.assert_called_once()

    @pytest.mark.asyncio
    async def test_teleport_in_same_map_basic(self, player_map_service, mock_message_sender):
        """Test teletransporte básico dentro del mismo mapa."""
        await player_map_service.teleport_in_same_map(
            user_id=1,
            map_id=1,
            old_x=50,
            old_y=50,
            new_x=80,
            new_y=80,
            heading=2,
            message_sender=mock_message_sender,
        )

        # Debe actualizar posición en Redis
        player_map_service.player_repo.set_position.assert_called_once_with(1, 80, 80, 1, 2)

        # Debe actualizar índice espacial
        player_map_service.map_manager.update_player_tile.assert_called_once_with(
            1, 1, 50, 50, 80, 80
        )

        # Debe enviar POS_UPDATE
        mock_message_sender.send_pos_update.assert_called_once_with(80, 80)

    @pytest.mark.asyncio
    async def test_teleport_in_same_map_broadcasts(self, player_map_service, mock_message_sender):
        """Test que teleport_in_same_map hace broadcast correctamente."""
        await player_map_service.teleport_in_same_map(
            user_id=1,
            map_id=1,
            old_x=50,
            old_y=50,
            new_x=80,
            new_y=80,
            heading=3,
            message_sender=mock_message_sender,
        )

        # Debe hacer broadcast de CHARACTER_REMOVE en posición anterior
        player_map_service.broadcast_service.broadcast_character_remove.assert_called_once_with(
            1, 1
        )

        # Debe hacer broadcast de CHARACTER_CREATE en nueva posición
        player_map_service.broadcast_service.broadcast_character_create.assert_called_once()
        call_args = player_map_service.broadcast_service.broadcast_character_create.call_args
        assert call_args.kwargs["map_id"] == 1
        assert call_args.kwargs["char_index"] == 1
        assert call_args.kwargs["x"] == 80
        assert call_args.kwargs["y"] == 80
        assert call_args.kwargs["heading"] == 3

    @pytest.mark.asyncio
    async def test_teleport_in_same_map_no_change_map(
        self, player_map_service, mock_message_sender
    ):
        """Test que teleport_in_same_map NO envía CHANGE_MAP (a diferencia de transition_to_map)."""
        await player_map_service.teleport_in_same_map(
            user_id=1,
            map_id=1,
            old_x=50,
            old_y=50,
            new_x=80,
            new_y=80,
            heading=3,
            message_sender=mock_message_sender,
        )

        # NO debe enviar CHANGE_MAP (eso es solo para transition_to_map)
        mock_message_sender.send_change_map.assert_not_called()

    @pytest.mark.asyncio
    async def test_teleport_in_same_map_no_map_manager_changes(
        self, player_map_service, mock_message_sender
    ):
        """Test que teleport_in_same_map NO remueve/agrega del MapManager (solo actualiza tile)."""
        await player_map_service.teleport_in_same_map(
            user_id=1,
            map_id=1,
            old_x=50,
            old_y=50,
            new_x=80,
            new_y=80,
            heading=3,
            message_sender=mock_message_sender,
        )

        # NO debe remover/agregar del MapManager (solo actualizar tile)
        player_map_service.map_manager.remove_player.assert_not_called()
        player_map_service.map_manager.add_player.assert_not_called()

        # Solo debe actualizar el tile
        player_map_service.map_manager.update_player_tile.assert_called_once()
