"""Tests para el sistema de movimiento de NPCs."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.effect_npc_movement import NPCMovementEffect
from src.npc import NPC


def create_test_npc(
    npc_id: int = 1,
    char_index: int = 10001,
    x: int = 50,
    y: int = 50,
    name: str = "Test NPC",
) -> NPC:
    """Crea un NPC de prueba con valores por defecto.

    Args:
        npc_id: ID del tipo de NPC.
        char_index: CharIndex único.
        x: Posición X.
        y: Posición Y.
        name: Nombre del NPC.

    Returns:
        Instancia de NPC configurada para tests.
    """
    return NPC(
        npc_id=npc_id,
        char_index=char_index,
        instance_id=f"test-npc-{char_index}",
        map_id=1,
        x=x,
        y=y,
        heading=3,
        name=name,
        description=f"Test {name}",
        body_id=500,
        head_id=0,
        hp=100,
        max_hp=100,
        level=1,
        is_hostile=npc_id in {1, 7},  # Goblin y Lobo son hostiles
        is_attackable=True,
        movement_type="random",
        respawn_time=60,
        gold_min=10,
        gold_max=50,
    )


class TestNPCMovementEffect:
    """Tests para el efecto de movimiento de NPCs."""

    @pytest.mark.asyncio
    async def test_movement_effect_basic(self) -> None:
        """Test básico del efecto de movimiento."""
        # Setup
        npc_service = MagicMock()
        npc_service.map_manager.get_all_npcs.return_value = []

        effect = NPCMovementEffect(npc_service, interval_seconds=5.0)

        # Verificar configuración
        assert effect.get_interval_seconds() == 5.0
        assert effect.get_name() == "NPCMovement"

    @pytest.mark.asyncio
    async def test_movement_effect_no_npcs(self) -> None:
        """Test cuando no hay NPCs en el mundo."""
        # Setup
        npc_service = MagicMock()
        npc_service.map_manager.get_all_npcs.return_value = []

        player_repo = MagicMock()
        message_sender = MagicMock()

        effect = NPCMovementEffect(npc_service, interval_seconds=5.0)

        # Execute
        await effect.apply(1, player_repo, message_sender)

        # Assert - no debe intentar mover NPCs
        npc_service.move_npc.assert_not_called()

    @pytest.mark.asyncio
    async def test_movement_effect_with_hostile_npc(self) -> None:
        """Test movimiento de NPC hostil sin jugadores cerca."""
        # Setup
        npc = create_test_npc(npc_id=1, name="Goblin")

        npc_service = MagicMock()
        npc_service.map_manager.get_all_npcs.return_value = [npc]
        npc_service.map_manager.get_players_in_map.return_value = []
        npc_service.move_npc = AsyncMock()

        player_repo = MagicMock()
        message_sender = MagicMock()

        effect = NPCMovementEffect(npc_service, interval_seconds=5.0)

        # Execute
        await effect.apply(1, player_repo, message_sender)

        # Assert - debe mover el NPC aleatoriamente
        npc_service.move_npc.assert_called_once()

    @pytest.mark.asyncio
    async def test_movement_effect_npc_pursues_player(self) -> None:
        """Test NPC persigue a jugador cercano."""
        # Setup
        npc = create_test_npc(npc_id=7, name="Lobo")

        npc_service = MagicMock()
        npc_service.map_manager.get_all_npcs.return_value = [npc]
        npc_service.map_manager.get_players_in_map.return_value = [1]
        npc_service.move_npc = AsyncMock()

        player_repo = MagicMock()
        player_repo.get_position = AsyncMock(
            return_value={"map": 1, "x": 52, "y": 50, "heading": 4}  # 2 tiles al este
        )

        message_sender = MagicMock()

        effect = NPCMovementEffect(npc_service, interval_seconds=5.0)

        # Execute
        await effect.apply(1, player_repo, message_sender)

        # Assert - debe moverse hacia el jugador (hacia el este)
        npc_service.move_npc.assert_called_once()
        call_args = npc_service.move_npc.call_args[0]
        assert call_args[0] == npc
        assert call_args[1] == 51  # x + 1 (hacia el este)
        assert call_args[2] == 50  # y sin cambio
        assert call_args[3] == 2  # heading = Este

    @pytest.mark.asyncio
    async def test_movement_effect_npc_ignores_far_player(self) -> None:
        """Test NPC ignora jugador lejano (fuera de rango)."""
        # Setup
        npc = create_test_npc(npc_id=1, name="Goblin")

        npc_service = MagicMock()
        npc_service.map_manager.get_all_npcs.return_value = [npc]
        npc_service.map_manager.get_players_in_map.return_value = [1]
        npc_service.move_npc = AsyncMock()

        player_repo = MagicMock()
        player_repo.get_position = AsyncMock(
            return_value={"map": 1, "x": 65, "y": 50, "heading": 4}  # 15 tiles de distancia
        )

        message_sender = MagicMock()

        effect = NPCMovementEffect(npc_service, interval_seconds=5.0)

        # Execute
        await effect.apply(1, player_repo, message_sender)

        # Assert - debe moverse aleatoriamente (no perseguir)
        npc_service.move_npc.assert_called_once()

    @pytest.mark.asyncio
    async def test_movement_effect_friendly_npc_doesnt_move(self) -> None:
        """Test NPC amigable no se mueve."""
        # Setup
        npc = create_test_npc(npc_id=2, name="Comerciante")

        npc_service = MagicMock()
        npc_service.map_manager.get_all_npcs.return_value = [npc]
        npc_service.move_npc = AsyncMock()

        player_repo = MagicMock()
        message_sender = MagicMock()

        effect = NPCMovementEffect(npc_service, interval_seconds=5.0)

        # Execute
        await effect.apply(1, player_repo, message_sender)

        # Assert - no debe mover NPCs amigables
        npc_service.move_npc.assert_not_called()

    @pytest.mark.asyncio
    async def test_movement_effect_multiple_players_targets_closest(self) -> None:
        """Test NPC persigue al jugador más cercano."""
        # Setup
        npc = create_test_npc(npc_id=7, name="Lobo")

        npc_service = MagicMock()
        npc_service.map_manager.get_all_npcs.return_value = [npc]
        npc_service.map_manager.get_players_in_map.return_value = [1, 2]
        npc_service.move_npc = AsyncMock()

        player_repo = MagicMock()

        async def get_position_side_effect(user_id: int) -> dict[str, int]:
            if user_id == 1:
                return {"map": 1, "x": 55, "y": 50, "heading": 4}  # 5 tiles
            return {"map": 1, "x": 52, "y": 50, "heading": 4}  # 2 tiles (más cercano)

        player_repo.get_position = AsyncMock(side_effect=get_position_side_effect)

        message_sender = MagicMock()

        effect = NPCMovementEffect(npc_service, interval_seconds=5.0)

        # Execute
        await effect.apply(1, player_repo, message_sender)

        # Assert - debe moverse hacia el jugador más cercano (user_id=2)
        npc_service.move_npc.assert_called_once()
        call_args = npc_service.move_npc.call_args[0]
        assert call_args[1] == 51  # Moverse hacia x=52 (jugador 2)

    @pytest.mark.asyncio
    async def test_movement_effect_executes_once_per_tick(self) -> None:
        """Test que el efecto se ejecuta solo una vez por tick."""
        # Setup
        npc_service = MagicMock()
        npc_service.map_manager.get_all_npcs.return_value = []

        player_repo = MagicMock()
        message_sender = MagicMock()

        effect = NPCMovementEffect(npc_service, interval_seconds=5.0)

        # Execute - llamar dos veces seguidas
        await effect.apply(1, player_repo, message_sender)
        await effect.apply(2, player_repo, message_sender)

        # Assert - get_all_npcs solo debe llamarse una vez
        assert npc_service.map_manager.get_all_npcs.call_count == 1
