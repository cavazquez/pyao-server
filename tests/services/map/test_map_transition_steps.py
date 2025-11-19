"""Tests para los pasos de transición de mapa."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.map.map_transition_steps import (
    AddToNewMapStep,
    BroadcastCreateInNewMapStep,
    BroadcastRemoveFromOldMapStep,
    ClientLoadDelayStep,
    MapTransitionContext,
    MapTransitionOrchestrator,
    RemoveFromOldMapStep,
    SendChangeMapStep,
    SendGroundItemsStep,
    SendNPCsStep,
    SendPositionUpdateStep,
    SendSelfCharacterCreateStep,
    UpdatePositionStep,
)


@pytest.fixture
def mock_context():
    """Contexto de transición para tests."""
    return MapTransitionContext(
        user_id=1,
        username="TestPlayer",
        char_body=1,
        char_head=1,
        current_map=1,
        current_x=50,
        current_y=50,
        new_map=2,
        new_x=100,
        new_y=100,
        heading=3,
        message_sender=MagicMock(),
    )


class TestSendChangeMapStep:
    """Tests para SendChangeMapStep."""

    @pytest.mark.asyncio
    async def test_execute_sends_change_map(self, mock_context):
        """Test que envía CHANGE_MAP."""
        mock_context.message_sender.send_change_map = AsyncMock()
        step = SendChangeMapStep()

        await step.execute(mock_context)

        mock_context.message_sender.send_change_map.assert_awaited_once_with(2)


class TestClientLoadDelayStep:
    """Tests para ClientLoadDelayStep."""

    @pytest.mark.asyncio
    async def test_execute_waits_specified_delay(self, mock_context):
        """Test que espera el delay especificado."""
        step = ClientLoadDelayStep(0.05)

        start_time = asyncio.get_event_loop().time()
        await step.execute(mock_context)
        end_time = asyncio.get_event_loop().time()

        assert end_time - start_time >= 0.05


class TestUpdatePositionStep:
    """Tests para UpdatePositionStep."""

    @pytest.mark.asyncio
    async def test_execute_updates_position_in_redis(self, mock_context):
        """Test que actualiza posición en Redis."""
        player_repo = AsyncMock()
        step = UpdatePositionStep(player_repo)

        await step.execute(mock_context)

        player_repo.set_position.assert_awaited_once_with(1, 100, 100, 2, 3)


class TestSendPositionUpdateStep:
    """Tests para SendPositionUpdateStep."""

    @pytest.mark.asyncio
    async def test_execute_sends_position_update(self, mock_context):
        """Test que envía POS_UPDATE."""
        mock_context.message_sender.send_pos_update = AsyncMock()
        step = SendPositionUpdateStep()

        await step.execute(mock_context)

        mock_context.message_sender.send_pos_update.assert_awaited_once_with(100, 100)


class TestRemoveFromOldMapStep:
    """Tests para RemoveFromOldMapStep."""

    @pytest.mark.asyncio
    async def test_execute_removes_from_old_map(self, mock_context):
        """Test que remueve del mapa anterior."""
        map_manager = MagicMock()
        step = RemoveFromOldMapStep(map_manager)

        await step.execute(mock_context)

        map_manager.remove_player.assert_called_once_with(1, 1)


class TestBroadcastRemoveFromOldMapStep:
    """Tests para BroadcastRemoveFromOldMapStep."""

    @pytest.mark.asyncio
    async def test_execute_broadcasts_remove(self, mock_context):
        """Test que envía broadcast de remoción."""
        broadcast_service = AsyncMock()
        step = BroadcastRemoveFromOldMapStep(broadcast_service)

        await step.execute(mock_context)

        broadcast_service.broadcast_character_remove.assert_awaited_once_with(1, 1)


class TestAddToNewMapStep:
    """Tests para AddToNewMapStep."""

    @pytest.mark.asyncio
    async def test_execute_adds_to_new_map(self, mock_context):
        """Test que agrega al nuevo mapa."""
        map_manager = MagicMock()
        step = AddToNewMapStep(map_manager)

        await step.execute(mock_context)

        map_manager.add_player.assert_called_once_with(
            2, 1, mock_context.message_sender, "TestPlayer"
        )


class TestSendSelfCharacterCreateStep:
    """Tests para SendSelfCharacterCreateStep."""

    @pytest.mark.asyncio
    async def test_execute_sends_self_character_create(self, mock_context):
        """Test que envía CHARACTER_CREATE propio."""
        mock_context.message_sender.send_character_create = AsyncMock()
        step = SendSelfCharacterCreateStep()

        await step.execute(mock_context)

        mock_context.message_sender.send_character_create.assert_awaited_once_with(
            char_index=1,
            body=1,
            head=1,
            heading=3,
            x=100,
            y=100,
            name="TestPlayer",
        )


class TestSendNPCsStep:
    """Tests para SendNPCsStep."""

    @pytest.mark.asyncio
    async def test_execute_sends_npcs(self, mock_context):
        """Test que envía NPCs del mapa."""
        send_npcs = AsyncMock()
        step = SendNPCsStep(send_npcs)

        await step.execute(mock_context)

        send_npcs.assert_awaited_once_with(mock_context.new_map, mock_context.message_sender)


class TestSendGroundItemsStep:
    """Tests para SendGroundItemsStep."""

    @pytest.mark.asyncio
    async def test_execute_sends_ground_items(self, mock_context):
        """Test que envía objetos del suelo."""
        send_ground_items = AsyncMock()
        step = SendGroundItemsStep(send_ground_items)

        await step.execute(mock_context)

        send_ground_items.assert_awaited_once_with(
            mock_context.new_map, mock_context.message_sender
        )


class TestBroadcastCreateInNewMapStep:
    """Tests para BroadcastCreateInNewMapStep."""

    @pytest.mark.asyncio
    async def test_execute_broadcasts_create(self, mock_context):
        """Test que envía broadcast de creación."""
        broadcast_service = AsyncMock()
        step = BroadcastCreateInNewMapStep(broadcast_service)

        await step.execute(mock_context)

        broadcast_service.broadcast_character_create.assert_awaited_once_with(
            map_id=2,
            char_index=1,
            body=1,
            head=1,
            heading=3,
            x=100,
            y=100,
            name="TestPlayer",
        )


class TestMapTransitionOrchestrator:
    """Tests para MapTransitionOrchestrator."""

    @pytest.mark.asyncio
    async def test_execute_transition_runs_all_steps(self, mock_context):
        """Test que ejecuta todos los pasos en orden."""
        step1 = AsyncMock()
        step2 = AsyncMock()
        step3 = AsyncMock()

        orchestrator = MapTransitionOrchestrator([step1, step2, step3])

        await orchestrator.execute_transition(mock_context)

        # Verificar que todos los pasos se ejecutaron
        step1.execute.assert_awaited_once_with(mock_context)
        step2.execute.assert_awaited_once_with(mock_context)
        step3.execute.assert_awaited_once_with(mock_context)

    @pytest.mark.asyncio
    async def test_execute_transition_handles_step_failure(self, mock_context):
        """Test que maneja fallos en los pasos."""
        step1 = AsyncMock()
        step2 = AsyncMock()
        step2.execute.side_effect = Exception("Test error")
        step3 = AsyncMock()

        orchestrator = MapTransitionOrchestrator([step1, step2, step3])

        with pytest.raises(Exception, match="Test error"):
            await orchestrator.execute_transition(mock_context)

        # Verificar que los pasos anteriores se ejecutaron
        step1.execute.assert_awaited_once_with(mock_context)
        step2.execute.assert_awaited_once_with(mock_context)
        # step3 no debe ejecutarse debido al fallo
        step3.execute.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_create_default_orchestrator(self):
        """Test que crea orquestador con pasos predeterminados."""
        player_repo = AsyncMock()
        map_manager = MagicMock()
        broadcast_service = AsyncMock()
        send_players = AsyncMock()
        send_npcs = AsyncMock()
        send_ground_items = AsyncMock()

        orchestrator = MapTransitionOrchestrator.create_default_orchestrator(
            player_repo,
            map_manager,
            broadcast_service,
            send_players,
            send_npcs,
            send_ground_items,
        )

        # Verificar que tiene 13 pasos (incluyendo actualización de tile en nuevo mapa)
        assert len(orchestrator.steps) == 13

        # Verificar tipos de pasos
        step_types = [type(step).__name__ for step in orchestrator.steps]
        expected_types = [
            "SendChangeMapStep",
            "ClientLoadDelayStep",
            "UpdatePositionStep",
            "SendPositionUpdateStep",
            "RemoveFromOldMapStep",
            "BroadcastRemoveFromOldMapStep",
            "AddToNewMapStep",
            "UpdateTileInNewMapStep",
            "SendSelfCharacterCreateStep",
            "SendExistingPlayersStep",
            "SendNPCsStep",
            "SendGroundItemsStep",
            "BroadcastCreateInNewMapStep",
        ]
        assert step_types == expected_types
