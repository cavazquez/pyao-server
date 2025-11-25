"""Tests adicionales para NPCAIService - métodos no cubiertos."""

import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.models.npc import NPC
from src.services.npc.npc_ai_service import NPCAIService


@pytest.fixture
def sample_npc() -> NPC:
    """Crea un NPC de prueba."""
    return NPC(
        npc_id=1,
        char_index=10001,
        instance_id="test-instance-1",
        map_id=1,
        x=50,
        y=50,
        heading=3,
        name="Orco",
        description="Un orco hostil",
        body_id=100,
        head_id=0,
        hp=50,
        max_hp=100,
        level=5,
        is_hostile=True,
        is_attackable=True,
        aggro_range=8,
        attack_damage=10,
        attack_cooldown=3.0,
        last_attack_time=0.0,
    )


@pytest.fixture
def mock_npc_service() -> MagicMock:
    """Crea un mock de NPCService."""
    return MagicMock()


@pytest.fixture
def mock_map_manager() -> MagicMock:
    """Crea un mock de MapManager."""
    return MagicMock()


@pytest.fixture
def mock_player_repo() -> MagicMock:
    """Crea un mock de PlayerRepository."""
    repo = MagicMock()
    repo.get_stats = AsyncMock()
    repo.get_position = AsyncMock()
    repo.update_hp = AsyncMock()
    return repo


@pytest.fixture
def mock_combat_service() -> MagicMock:
    """Crea un mock de CombatService."""
    service = MagicMock()
    service.npc_attack_player = AsyncMock()
    return service


@pytest.fixture
def mock_broadcast_service() -> MagicMock:
    """Crea un mock de MultiplayerBroadcastService."""
    service = MagicMock()
    service.broadcast_character_move = AsyncMock()
    return service


@pytest.fixture
def ai_service(
    mock_npc_service: MagicMock,
    mock_map_manager: MagicMock,
    mock_player_repo: MagicMock,
    mock_combat_service: MagicMock,
    mock_broadcast_service: MagicMock,
) -> NPCAIService:
    """Crea una instancia de NPCAIService con mocks."""
    return NPCAIService(
        npc_service=mock_npc_service,
        map_manager=mock_map_manager,
        player_repo=mock_player_repo,
        combat_service=mock_combat_service,
        broadcast_service=mock_broadcast_service,
    )


class TestFindNearestPlayer:
    """Tests para find_nearest_player."""

    @pytest.mark.asyncio
    async def test_find_nearest_player_no_players(
        self,
        ai_service: NPCAIService,
        sample_npc: NPC,
        mock_map_manager: MagicMock,
    ) -> None:
        """Test cuando no hay jugadores en el mapa."""
        mock_map_manager.get_players_in_map.return_value = []

        result = await ai_service.find_nearest_player(sample_npc)

        assert result is None

    @pytest.mark.asyncio
    async def test_find_nearest_player_dead_player(
        self,
        ai_service: NPCAIService,
        sample_npc: NPC,
        mock_map_manager: MagicMock,
        mock_player_repo: MagicMock,
    ) -> None:
        """Test cuando el jugador está muerto."""
        mock_map_manager.get_players_in_map.return_value = [1]
        mock_player_repo.get_stats = AsyncMock(return_value={"min_hp": 0})  # Muerto

        result = await ai_service.find_nearest_player(sample_npc)

        assert result is None

    @pytest.mark.asyncio
    async def test_find_nearest_player_different_map(
        self,
        ai_service: NPCAIService,
        sample_npc: NPC,
        mock_map_manager: MagicMock,
        mock_player_repo: MagicMock,
    ) -> None:
        """Test cuando el jugador está en otro mapa."""
        mock_map_manager.get_players_in_map.return_value = [1]
        mock_player_repo.get_stats = AsyncMock(return_value={"min_hp": 100})
        mock_player_repo.get_position = AsyncMock(
            return_value={"map": 2, "x": 50, "y": 50}
        )  # Mapa diferente

        result = await ai_service.find_nearest_player(sample_npc)

        assert result is None

    @pytest.mark.asyncio
    async def test_find_nearest_player_out_of_range(
        self,
        ai_service: NPCAIService,
        sample_npc: NPC,
        mock_map_manager: MagicMock,
        mock_player_repo: MagicMock,
    ) -> None:
        """Test cuando el jugador está fuera de rango."""
        sample_npc.aggro_range = 5
        mock_map_manager.get_players_in_map.return_value = [1]
        mock_player_repo.get_stats = AsyncMock(return_value={"min_hp": 100})
        mock_player_repo.get_position = AsyncMock(
            return_value={"map": 1, "x": 100, "y": 100}
        )  # Muy lejos

        result = await ai_service.find_nearest_player(sample_npc)

        assert result is None

    @pytest.mark.asyncio
    async def test_find_nearest_player_found(
        self,
        ai_service: NPCAIService,
        sample_npc: NPC,
        mock_map_manager: MagicMock,
        mock_player_repo: MagicMock,
    ) -> None:
        """Test encontrar jugador más cercano."""
        sample_npc.aggro_range = 10
        mock_map_manager.get_players_in_map.return_value = [1, 2]
        mock_player_repo.get_stats = AsyncMock(return_value={"min_hp": 100})
        # Jugador 1 más cerca, jugador 2 más lejos
        mock_player_repo.get_position = AsyncMock(
            side_effect=[
                {"map": 1, "x": 51, "y": 50},  # Distancia 1
                {"map": 1, "x": 55, "y": 50},  # Distancia 5
            ]
        )

        result = await ai_service.find_nearest_player(sample_npc)

        assert result is not None
        user_id, x, y = result
        assert user_id == 1  # Jugador más cercano
        assert x == 51
        assert y == 50


class TestGetDirectionToTarget:
    """Tests para get_direction_to_target."""

    def test_get_direction_to_target_north(self, ai_service: NPCAIService) -> None:
        """Test dirección Norte."""
        direction = ai_service.get_direction_to_target(50, 50, 50, 40)
        assert direction == 1  # Norte

    def test_get_direction_to_target_south(self, ai_service: NPCAIService) -> None:
        """Test dirección Sur."""
        direction = ai_service.get_direction_to_target(50, 50, 50, 60)
        assert direction == 3  # Sur

    def test_get_direction_to_target_east(self, ai_service: NPCAIService) -> None:
        """Test dirección Este."""
        direction = ai_service.get_direction_to_target(50, 50, 60, 50)
        assert direction == 2  # Este

    def test_get_direction_to_target_west(self, ai_service: NPCAIService) -> None:
        """Test dirección Oeste."""
        direction = ai_service.get_direction_to_target(50, 50, 40, 50)
        assert direction == 4  # Oeste

    def test_get_direction_to_target_prioritize_horizontal(self, ai_service: NPCAIService) -> None:
        """Test que prioriza movimiento horizontal cuando abs(dx) > abs(dy)."""
        # dx=5, dy=3 -> prioriza horizontal
        direction = ai_service.get_direction_to_target(50, 50, 55, 53)
        assert direction == 2  # Este

    def test_get_direction_to_target_prioritize_vertical(self, ai_service: NPCAIService) -> None:
        """Test que prioriza movimiento vertical cuando abs(dy) > abs(dx)."""
        # dx=3, dy=5 -> prioriza vertical
        direction = ai_service.get_direction_to_target(50, 50, 53, 55)
        assert direction == 3  # Sur


class TestTryAttackPlayer:
    """Tests para try_attack_player."""

    @pytest.mark.asyncio
    async def test_try_attack_player_dead_player(
        self,
        ai_service: NPCAIService,
        sample_npc: NPC,
        mock_player_repo: MagicMock,
    ) -> None:
        """Test atacar jugador muerto."""
        mock_player_repo.get_stats = AsyncMock(return_value={"min_hp": 0})

        result = await ai_service.try_attack_player(sample_npc, 1)

        assert result is False

    @pytest.mark.asyncio
    async def test_try_attack_player_no_position(
        self,
        ai_service: NPCAIService,
        sample_npc: NPC,
        mock_player_repo: MagicMock,
    ) -> None:
        """Test atacar jugador sin posición."""
        mock_player_repo.get_stats = AsyncMock(return_value={"min_hp": 100})
        mock_player_repo.get_position = AsyncMock(return_value=None)

        result = await ai_service.try_attack_player(sample_npc, 1)

        assert result is False

    @pytest.mark.asyncio
    async def test_try_attack_player_different_map(
        self,
        ai_service: NPCAIService,
        sample_npc: NPC,
        mock_player_repo: MagicMock,
    ) -> None:
        """Test atacar jugador en otro mapa."""
        mock_player_repo.get_stats = AsyncMock(return_value={"min_hp": 100})
        mock_player_repo.get_position = AsyncMock(return_value={"map": 2, "x": 51, "y": 50})

        result = await ai_service.try_attack_player(sample_npc, 1)

        assert result is False

    @pytest.mark.asyncio
    async def test_try_attack_player_not_adjacent(
        self,
        ai_service: NPCAIService,
        sample_npc: NPC,
        mock_player_repo: MagicMock,
    ) -> None:
        """Test atacar jugador no adyacente."""
        mock_player_repo.get_stats = AsyncMock(return_value={"min_hp": 100})
        mock_player_repo.get_position = AsyncMock(
            return_value={"map": 1, "x": 55, "y": 50}
        )  # Lejos

        result = await ai_service.try_attack_player(sample_npc, 1)

        assert result is False

    @pytest.mark.asyncio
    async def test_try_attack_player_cooldown(
        self,
        ai_service: NPCAIService,
        sample_npc: NPC,
        mock_player_repo: MagicMock,
    ) -> None:
        """Test atacar jugador en cooldown."""
        sample_npc.last_attack_time = time.time()  # Recién atacó
        sample_npc.attack_cooldown = 3.0
        mock_player_repo.get_stats = AsyncMock(return_value={"min_hp": 100})
        mock_player_repo.get_position = AsyncMock(
            return_value={"map": 1, "x": 51, "y": 50}
        )  # Adyacente

        result = await ai_service.try_attack_player(sample_npc, 1)

        assert result is False

    @pytest.mark.asyncio
    async def test_try_attack_player_success(
        self,
        ai_service: NPCAIService,
        sample_npc: NPC,
        mock_map_manager: MagicMock,
        mock_player_repo: MagicMock,
        mock_combat_service: MagicMock,
    ) -> None:
        """Test ataque exitoso."""
        sample_npc.last_attack_time = 0  # Sin cooldown
        mock_player_repo.get_stats = AsyncMock(return_value={"min_hp": 100})
        mock_player_repo.get_position = AsyncMock(
            return_value={"map": 1, "x": 51, "y": 50}
        )  # Adyacente
        mock_combat_service.npc_attack_player = AsyncMock(
            return_value={"damage": 10, "player_died": False}
        )

        message_sender = MagicMock()
        message_sender.send_npc_hit_user = AsyncMock()
        message_sender.send_play_wave = AsyncMock()
        message_sender.send_create_fx = AsyncMock()
        message_sender.send_update_user_stats = AsyncMock()
        mock_map_manager.get_message_sender = MagicMock(return_value=message_sender)

        result = await ai_service.try_attack_player(sample_npc, 1)

        assert result is True
        mock_combat_service.npc_attack_player.assert_called_once()
        message_sender.send_npc_hit_user.assert_called_once()

    @pytest.mark.asyncio
    async def test_try_attack_player_player_died(
        self,
        ai_service: NPCAIService,
        sample_npc: NPC,
        mock_map_manager: MagicMock,
        mock_player_repo: MagicMock,
        mock_combat_service: MagicMock,
    ) -> None:
        """Test ataque que mata al jugador."""
        sample_npc.last_attack_time = 0
        mock_player_repo.get_stats = AsyncMock(
            side_effect=[
                {"min_hp": 100},  # Primera llamada (verificar vivo)
                {"min_hp": 0, "max_hp": 100},  # Segunda llamada (después del ataque)
            ]
        )
        mock_player_repo.get_position = AsyncMock(return_value={"map": 1, "x": 51, "y": 50})
        mock_player_repo.update_hp = AsyncMock()
        mock_combat_service.npc_attack_player = AsyncMock(
            return_value={"damage": 100, "player_died": True}
        )

        message_sender = MagicMock()
        message_sender.send_npc_hit_user = AsyncMock()
        message_sender.send_play_wave = AsyncMock()
        message_sender.send_create_fx = AsyncMock()
        message_sender.send_console_msg = AsyncMock()
        message_sender.send_update_user_stats = AsyncMock()
        mock_map_manager.get_message_sender = MagicMock(return_value=message_sender)

        result = await ai_service.try_attack_player(sample_npc, 1)

        assert result is True
        mock_player_repo.update_hp.assert_called_once()  # Revive al jugador
        message_sender.send_console_msg.assert_called()


class TestTryMoveTowards:
    """Tests para try_move_towards."""

    @pytest.mark.asyncio
    async def test_try_move_towards_with_pathfinding(
        self,
        ai_service: NPCAIService,
        sample_npc: NPC,
        mock_map_manager: MagicMock,
        mock_broadcast_service: MagicMock,
    ) -> None:
        """Test movimiento con pathfinding."""
        pathfinding_service = MagicMock()
        pathfinding_service.get_next_step = MagicMock(return_value=(51, 50, 2))  # x, y, direction
        ai_service.pathfinding_service = pathfinding_service

        mock_map_manager.is_tile_occupied = MagicMock(return_value=False)
        mock_map_manager.move_npc = MagicMock()

        result = await ai_service.try_move_towards(sample_npc, 60, 50)

        assert result is True
        assert sample_npc.x == 51
        assert sample_npc.y == 50
        mock_map_manager.move_npc.assert_called_once()
        mock_broadcast_service.broadcast_character_move.assert_called_once()

    @pytest.mark.asyncio
    async def test_try_move_towards_pathfinding_tile_occupied(
        self,
        ai_service: NPCAIService,
        sample_npc: NPC,
        mock_map_manager: MagicMock,
    ) -> None:
        """Test movimiento con pathfinding cuando el tile está ocupado."""
        pathfinding_service = MagicMock()
        pathfinding_service.get_next_step = MagicMock(return_value=(51, 50, 2))
        ai_service.pathfinding_service = pathfinding_service

        mock_map_manager.is_tile_occupied = MagicMock(return_value=True)  # Tile ocupado

        result = await ai_service.try_move_towards(sample_npc, 60, 50)

        assert result is False

    @pytest.mark.asyncio
    async def test_try_move_towards_pathfinding_no_path(
        self,
        ai_service: NPCAIService,
        sample_npc: NPC,
    ) -> None:
        """Test movimiento con pathfinding sin camino."""
        pathfinding_service = MagicMock()
        pathfinding_service.get_next_step = MagicMock(return_value=None)  # Sin camino
        ai_service.pathfinding_service = pathfinding_service

        result = await ai_service.try_move_towards(sample_npc, 60, 50)

        assert result is False

    @pytest.mark.asyncio
    async def test_try_move_towards_simple_movement(
        self,
        ai_service: NPCAIService,
        sample_npc: NPC,
        mock_map_manager: MagicMock,
    ) -> None:
        """Test movimiento simple sin pathfinding."""
        ai_service.pathfinding_service = None  # Sin pathfinding

        mock_map_manager.can_move_to = MagicMock(return_value=True)
        mock_map_manager.is_tile_occupied = MagicMock(return_value=False)
        mock_map_manager.move_npc = MagicMock()

        result = await ai_service.try_move_towards(sample_npc, 60, 50)  # Este

        assert result is True
        assert sample_npc.x == 51  # Se movió al Este
        assert sample_npc.y == 50
        mock_map_manager.move_npc.assert_called_once()

    @pytest.mark.asyncio
    async def test_try_move_towards_simple_movement_blocked(
        self,
        ai_service: NPCAIService,
        sample_npc: NPC,
        mock_map_manager: MagicMock,
    ) -> None:
        """Test movimiento simple cuando está bloqueado."""
        ai_service.pathfinding_service = None

        mock_map_manager.can_move_to = MagicMock(return_value=False)  # Bloqueado

        result = await ai_service.try_move_towards(sample_npc, 60, 50)

        assert result is False

    @pytest.mark.asyncio
    async def test_try_move_towards_simple_movement_occupied(
        self,
        ai_service: NPCAIService,
        sample_npc: NPC,
        mock_map_manager: MagicMock,
    ) -> None:
        """Test movimiento simple cuando el tile está ocupado."""
        ai_service.pathfinding_service = None

        mock_map_manager.can_move_to = MagicMock(return_value=True)
        mock_map_manager.is_tile_occupied = MagicMock(return_value=True)  # Ocupado

        result = await ai_service.try_move_towards(sample_npc, 60, 50)

        assert result is False


class TestProcessHostileNPC:
    """Tests para process_hostile_npc."""

    @pytest.mark.asyncio
    async def test_process_hostile_npc_not_hostile(
        self,
        ai_service: NPCAIService,
        sample_npc: NPC,
    ) -> None:
        """Test procesar NPC no hostil."""
        sample_npc.is_hostile = False

        # No debe hacer nada
        await ai_service.process_hostile_npc(sample_npc)

    @pytest.mark.asyncio
    async def test_process_hostile_npc_no_players(
        self,
        ai_service: NPCAIService,
        sample_npc: NPC,
        mock_map_manager: MagicMock,
    ) -> None:
        """Test procesar NPC hostil sin jugadores cerca."""
        mock_map_manager.get_players_in_map.return_value = []

        await ai_service.process_hostile_npc(sample_npc)

        # No debe hacer nada (comportamiento idle)

    @pytest.mark.asyncio
    async def test_process_hostile_npc_attack_adjacent(
        self,
        ai_service: NPCAIService,
        sample_npc: NPC,
        mock_map_manager: MagicMock,
        mock_player_repo: MagicMock,
        mock_combat_service: MagicMock,
    ) -> None:
        """Test procesar NPC hostil que ataca jugador adyacente."""
        mock_map_manager.get_players_in_map.return_value = [1]
        mock_player_repo.get_stats = AsyncMock(return_value={"min_hp": 100})
        mock_player_repo.get_position = AsyncMock(
            return_value={"map": 1, "x": 51, "y": 50}
        )  # Adyacente
        mock_combat_service.npc_attack_player = AsyncMock(return_value={"damage": 10})

        message_sender = MagicMock()
        message_sender.send_npc_hit_user = AsyncMock()
        message_sender.send_play_wave = AsyncMock()
        message_sender.send_create_fx = AsyncMock()
        message_sender.send_update_user_stats = AsyncMock()
        mock_map_manager.get_message_sender = MagicMock(return_value=message_sender)

        sample_npc.last_attack_time = 0  # Sin cooldown

        await ai_service.process_hostile_npc(sample_npc)

        # Puede o no atacar dependiendo del random (30% skip)
        # Pero si ataca, debe llamar a try_attack_player

    @pytest.mark.asyncio
    async def test_process_hostile_npc_move_towards(
        self,
        ai_service: NPCAIService,
        sample_npc: NPC,
        mock_map_manager: MagicMock,
        mock_player_repo: MagicMock,
    ) -> None:
        """Test procesar NPC hostil que se mueve hacia jugador."""
        mock_map_manager.get_players_in_map.return_value = [1]
        mock_player_repo.get_stats = AsyncMock(return_value={"min_hp": 100})
        mock_player_repo.get_position = AsyncMock(
            return_value={"map": 1, "x": 55, "y": 50}
        )  # Lejos pero en rango
        mock_map_manager.can_move_to = MagicMock(return_value=True)
        mock_map_manager.is_tile_occupied = MagicMock(return_value=False)
        mock_map_manager.move_npc = MagicMock()

        ai_service.pathfinding_service = None  # Sin pathfinding

        await ai_service.process_hostile_npc(sample_npc)

        # Puede o no moverse dependiendo del random (50% probabilidad)
        # Pero si se mueve, debe llamar a try_move_towards
