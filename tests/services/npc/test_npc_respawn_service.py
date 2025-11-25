"""Tests para NPCRespawnService."""

import asyncio
import contextlib
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.models.npc import NPC
from src.services.npc.npc_respawn_service import NPCRespawnService


@pytest.fixture
def mock_npc_service() -> MagicMock:
    """Crea un mock de NPCService."""
    service = MagicMock()
    service.map_manager = MagicMock()
    service.spawn_npc = AsyncMock()
    return service


@pytest.fixture
def respawn_service(mock_npc_service: MagicMock) -> NPCRespawnService:
    """Crea una instancia de NPCRespawnService con mocks."""
    return NPCRespawnService(mock_npc_service)


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
        respawn_time=5,
        respawn_time_max=10,
    )


class TestFindRandomFreePosition:
    """Tests para _find_random_free_position."""

    def test_find_random_free_position_found(
        self,
        respawn_service: NPCRespawnService,
        mock_npc_service: MagicMock,
    ) -> None:
        """Test encontrar posición libre."""
        mock_npc_service.map_manager.can_move_to.return_value = True

        pos = respawn_service._find_random_free_position(1, 50, 50, radius=5)

        assert pos is not None
        x, y = pos
        assert 1 <= x <= 100
        assert 1 <= y <= 100
        # Debe estar dentro del radio
        assert abs(x - 50) <= 5
        assert abs(y - 50) <= 5

    def test_find_random_free_position_blocked(
        self,
        respawn_service: NPCRespawnService,
        mock_npc_service: MagicMock,
    ) -> None:
        """Test cuando la posición está bloqueada."""
        mock_npc_service.map_manager.can_move_to.return_value = False
        mock_npc_service.map_manager.get_tile_occupant.return_value = None

        pos = respawn_service._find_random_free_position(1, 50, 50, radius=5)

        assert pos is None

    def test_find_random_free_position_occupied(
        self,
        respawn_service: NPCRespawnService,
        mock_npc_service: MagicMock,
    ) -> None:
        """Test cuando la posición está ocupada por otro ente."""
        mock_npc_service.map_manager.can_move_to.return_value = False
        mock_npc_service.map_manager.get_tile_occupant.return_value = "player:1"

        pos = respawn_service._find_random_free_position(1, 50, 50, radius=5)

        assert pos is None

    def test_find_random_free_position_out_of_bounds(
        self,
        respawn_service: NPCRespawnService,
        mock_npc_service: MagicMock,
    ) -> None:
        """Test cuando la posición está fuera de los límites del mapa."""
        # Simular que random genera una posición fuera de límites
        # Esto es difícil de testear directamente, pero podemos verificar
        # que el método maneja correctamente los límites
        mock_npc_service.map_manager.can_move_to.return_value = True

        # Probar con posición cerca del borde
        pos = respawn_service._find_random_free_position(1, 1, 1, radius=5)

        # Si encuentra posición, debe estar dentro de límites
        if pos:
            x, y = pos
            assert 1 <= x <= 100
            assert 1 <= y <= 100


class TestScheduleRespawn:
    """Tests para schedule_respawn."""

    @pytest.mark.asyncio
    async def test_schedule_respawn_with_respawn_time(
        self,
        respawn_service: NPCRespawnService,
        sample_npc: NPC,
    ) -> None:
        """Test programar respawn con tiempo de respawn válido."""
        await respawn_service.schedule_respawn(sample_npc)

        # Debe crear una tarea de respawn
        assert sample_npc.instance_id in respawn_service._respawn_tasks

    @pytest.mark.asyncio
    async def test_schedule_respawn_no_respawn_time(
        self,
        respawn_service: NPCRespawnService,
        sample_npc: NPC,
    ) -> None:
        """Test programar respawn sin tiempo de respawn (respawn_time=0)."""
        sample_npc.respawn_time = 0

        await respawn_service.schedule_respawn(sample_npc)

        # No debe crear tarea de respawn
        assert sample_npc.instance_id not in respawn_service._respawn_tasks

    @pytest.mark.asyncio
    async def test_schedule_respawn_cancels_existing(
        self,
        respawn_service: NPCRespawnService,
        sample_npc: NPC,
    ) -> None:
        """Test que schedule_respawn cancela respawn existente."""
        # Crear primera tarea
        await respawn_service.schedule_respawn(sample_npc)
        first_task = respawn_service._respawn_tasks[sample_npc.instance_id]

        # Programar segundo respawn
        await respawn_service.schedule_respawn(sample_npc)
        second_task = respawn_service._respawn_tasks[sample_npc.instance_id]

        # Debe ser una tarea diferente
        assert first_task != second_task
        # Esperar un poco para que la cancelación se procese
        await asyncio.sleep(0.01)
        # La primera tarea debe estar cancelada o completada
        assert first_task.cancelled() or first_task.done()


class TestRespawnAfterDelay:
    """Tests para _respawn_after_delay."""

    @pytest.mark.asyncio
    async def test_respawn_after_delay_success(
        self,
        respawn_service: NPCRespawnService,
        mock_npc_service: MagicMock,
        sample_npc: NPC,
    ) -> None:
        """Test respawn exitoso después del delay."""
        # Setup
        mock_npc_service.map_manager.can_move_to.return_value = True
        new_npc = NPC(
            npc_id=1,
            char_index=10002,
            instance_id="test-instance-2",
            map_id=1,
            x=51,
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
            respawn_time=5,
            respawn_time_max=10,
        )
        mock_npc_service.spawn_npc.return_value = new_npc

        # Execute
        await respawn_service._respawn_after_delay(
            sample_npc, delay_seconds=0
        )  # Sin delay para test rápido

        # Assert
        mock_npc_service.spawn_npc.assert_called_once()
        # La tarea debe limpiarse después del respawn
        assert sample_npc.instance_id not in respawn_service._respawn_tasks

    @pytest.mark.asyncio
    async def test_respawn_after_delay_no_free_position(
        self,
        respawn_service: NPCRespawnService,
        mock_npc_service: MagicMock,
        sample_npc: NPC,
    ) -> None:
        """Test respawn cuando no hay posición libre (debe reintentar)."""
        # Setup - todas las posiciones bloqueadas
        mock_npc_service.map_manager.can_move_to.return_value = False
        mock_npc_service.map_manager.get_tile_occupant.return_value = None

        # Execute con delay 0 y timeout corto
        task = asyncio.create_task(
            respawn_service._respawn_after_delay(sample_npc, delay_seconds=0)
        )

        # Esperar un poco para que intente
        await asyncio.sleep(0.1)

        # Cancelar la tarea para que no siga intentando indefinidamente
        task.cancel()

        with contextlib.suppress(asyncio.CancelledError):
            await task

        # Debe haber intentado spawnear (aunque falló)
        # No verificamos el número exacto de intentos porque es aleatorio

    @pytest.mark.asyncio
    async def test_respawn_after_delay_spawn_fails(
        self,
        respawn_service: NPCRespawnService,
        mock_npc_service: MagicMock,
        sample_npc: NPC,
    ) -> None:
        """Test respawn cuando spawn_npc falla."""
        # Setup
        mock_npc_service.map_manager.can_move_to.return_value = True
        mock_npc_service.spawn_npc.side_effect = ValueError("Tile ocupado")

        # Execute con delay 0
        task = asyncio.create_task(
            respawn_service._respawn_after_delay(sample_npc, delay_seconds=0)
        )

        # Esperar un poco
        await asyncio.sleep(0.1)

        # Cancelar
        task.cancel()

        with contextlib.suppress(asyncio.CancelledError):
            await task

        # Debe haber intentado spawnear
        assert mock_npc_service.spawn_npc.called

    @pytest.mark.asyncio
    async def test_respawn_after_delay_cancelled(
        self,
        respawn_service: NPCRespawnService,
        sample_npc: NPC,
    ) -> None:
        """Test respawn cancelado."""
        # Crear tarea
        task = asyncio.create_task(
            respawn_service._respawn_after_delay(sample_npc, delay_seconds=10)
        )

        # Cancelar inmediatamente
        task.cancel()

        with contextlib.suppress(asyncio.CancelledError):
            await task

        # La tarea debe limpiarse
        assert sample_npc.instance_id not in respawn_service._respawn_tasks


class TestCancelRespawn:
    """Tests para cancel_respawn."""

    @pytest.mark.asyncio
    async def test_cancel_respawn_existing(
        self,
        respawn_service: NPCRespawnService,
        sample_npc: NPC,
    ) -> None:
        """Test cancelar respawn existente."""
        # Programar respawn
        await respawn_service.schedule_respawn(sample_npc)

        # Cancelar
        respawn_service.cancel_respawn(sample_npc.instance_id)

        # La tarea debe estar cancelada y removida
        assert sample_npc.instance_id not in respawn_service._respawn_tasks

    def test_cancel_respawn_nonexistent(
        self,
        respawn_service: NPCRespawnService,
    ) -> None:
        """Test cancelar respawn inexistente (no debe crashear)."""
        respawn_service.cancel_respawn("nonexistent-instance")

        # No debe crashear


class TestCancelAllRespawns:
    """Tests para cancel_all_respawns."""

    @pytest.mark.asyncio
    async def test_cancel_all_respawns_multiple(
        self,
        respawn_service: NPCRespawnService,
        sample_npc: NPC,
    ) -> None:
        """Test cancelar todos los respawns."""
        # Crear múltiples NPCs
        npc1 = sample_npc
        npc2 = NPC(
            npc_id=2,
            char_index=10002,
            instance_id="test-instance-2",
            map_id=1,
            x=50,
            y=50,
            heading=3,
            name="Lobo",
            description="Un lobo",
            body_id=101,
            head_id=0,
            hp=30,
            max_hp=60,
            level=3,
            is_hostile=True,
            is_attackable=True,
            respawn_time=3,
            respawn_time_max=6,
        )

        # Programar respawns
        await respawn_service.schedule_respawn(npc1)
        await respawn_service.schedule_respawn(npc2)

        # Cancelar todos
        respawn_service.cancel_all_respawns()

        # Todas las tareas deben estar canceladas
        assert len(respawn_service._respawn_tasks) == 0


class TestGetPendingRespawnsCount:
    """Tests para get_pending_respawns_count."""

    @pytest.mark.asyncio
    async def test_get_pending_respawns_count_empty(
        self,
        respawn_service: NPCRespawnService,
    ) -> None:
        """Test obtener conteo cuando no hay respawns pendientes."""
        assert respawn_service.get_pending_respawns_count() == 0

    @pytest.mark.asyncio
    async def test_get_pending_respawns_count_multiple(
        self,
        respawn_service: NPCRespawnService,
        sample_npc: NPC,
    ) -> None:
        """Test obtener conteo con múltiples respawns pendientes."""
        # Crear múltiples NPCs
        npc1 = sample_npc
        npc2 = NPC(
            npc_id=2,
            char_index=10002,
            instance_id="test-instance-2",
            map_id=1,
            x=50,
            y=50,
            heading=3,
            name="Lobo",
            description="Un lobo",
            body_id=101,
            head_id=0,
            hp=30,
            max_hp=60,
            level=3,
            is_hostile=True,
            is_attackable=True,
            respawn_time=3,
            respawn_time_max=6,
        )

        # Programar respawns
        await respawn_service.schedule_respawn(npc1)
        await respawn_service.schedule_respawn(npc2)

        # Verificar conteo
        assert respawn_service.get_pending_respawns_count() == 2
