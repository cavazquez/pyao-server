"""Tests para RandomSpawnService."""

import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.models.npc import NPC
from src.services.npc.random_spawn_service import (
    RandomSpawnService,
)


@pytest.fixture
def mock_npc_service() -> MagicMock:
    """Mock de NPCService."""
    service = MagicMock()
    service.npc_catalog = MagicMock()
    service.npc_catalog.get_all_npc_ids = MagicMock(return_value=[1, 2, 3])
    service.npc_catalog.get_npc_data = MagicMock(return_value={"es_hostil": True})
    service.spawn_npc = AsyncMock()
    return service


@pytest.fixture
def mock_map_manager() -> MagicMock:
    """Mock de MapManager."""
    manager = MagicMock()
    manager.can_move_to = MagicMock(return_value=True)
    manager.get_player_count_in_map = MagicMock(return_value=1)
    return manager


@pytest.fixture
def random_spawn_service(
    mock_npc_service: MagicMock, mock_map_manager: MagicMock
) -> RandomSpawnService:
    """Fixture para RandomSpawnService."""
    return RandomSpawnService(mock_npc_service, mock_map_manager)


@pytest.fixture
def sample_npc() -> NPC:
    """Fixture para un NPC de prueba."""
    return NPC(
        npc_id=1,
        char_index=10001,
        instance_id="test-instance-123",
        map_id=1,
        x=50,
        y=50,
        heading=3,
        name="Goblin",
        description="Un goblin",
        body_id=500,
        head_id=0,
        hp=100,
        max_hp=100,
        level=5,
        is_hostile=True,
        is_attackable=True,
        snd1=10,
        snd2=11,
        snd3=12,
    )


@pytest.fixture
def sample_spawn_config() -> dict:
    """Fixture para configuración de spawn."""
    return {
        "npc_type": "hostile",
        "count": 5,
        "area": {"x1": 70, "y1": 70, "x2": 90, "y2": 90},
    }


class TestRandomSpawnServiceInit:
    """Tests de inicialización de RandomSpawnService."""

    def test_init(self, random_spawn_service: RandomSpawnService) -> None:
        """Test de inicialización básica."""
        assert random_spawn_service.npc_service is not None
        assert random_spawn_service.map_manager is not None
        assert random_spawn_service._random_spawn_configs == {}
        assert random_spawn_service._random_spawned_npcs == {}
        assert random_spawn_service._respawn_cooldowns == {}


class TestLoadRandomSpawnConfigs:
    """Tests para cargar configuración de random spawns."""

    def test_load_configs_from_valid_file(
        self, random_spawn_service: RandomSpawnService, tmp_path: Path
    ) -> None:
        """Test cargar configuración desde archivo válido."""
        # Crear archivo TOML de prueba
        toml_content = """[map_npcs]
[map_npcs.1]
name = "Test Map"

[[map_npcs.1.random_spawns]]
npc_type = "hostile"
count = 5
area = {x1 = 70, y1 = 70, x2 = 90, y2 = 90}
"""
        config_file = tmp_path / "map_npcs.toml"
        config_file.write_text(toml_content)

        # Cargar configuración
        random_spawn_service.load_random_spawn_configs(config_file)

        # Verificar que se cargó
        assert 1 in random_spawn_service._random_spawn_configs
        configs = random_spawn_service._random_spawn_configs[1]
        assert len(configs) == 1
        assert configs[0]["npc_type"] == "hostile"
        assert configs[0]["count"] == 5

    def test_load_configs_missing_file(self, random_spawn_service: RandomSpawnService) -> None:
        """Test cargar configuración desde archivo inexistente."""
        random_spawn_service.load_random_spawn_configs("nonexistent.toml")

        # No debe fallar, solo debe estar vacío
        assert random_spawn_service._random_spawn_configs == {}

    def test_load_configs_invalid_toml(
        self, random_spawn_service: RandomSpawnService, tmp_path: Path
    ) -> None:
        """Test cargar configuración desde archivo TOML inválido."""
        invalid_file = tmp_path / "invalid.toml"
        invalid_file.write_text("invalid toml content [[")

        # No debe fallar, solo debe estar vacío
        random_spawn_service.load_random_spawn_configs(invalid_file)
        assert random_spawn_service._random_spawn_configs == {}


class TestSpawnRandomNPCsForPlayer:
    """Tests para spawnear NPCs aleatorios."""

    @pytest.mark.asyncio
    async def test_spawn_when_player_near_area(
        self,
        random_spawn_service: RandomSpawnService,
        sample_npc: NPC,
        sample_spawn_config: dict,
        mock_npc_service: MagicMock,
        mock_map_manager: MagicMock,
    ) -> None:
        """Test spawneear NPCs cuando jugador está cerca del área."""
        # Configurar servicio
        random_spawn_service._random_spawn_configs[1] = [sample_spawn_config]

        # Configurar mocks
        mock_npc_service.spawn_npc = AsyncMock(return_value=sample_npc)
        mock_npc_service.npc_catalog.get_all_npc_ids = MagicMock(return_value=[1, 2, 3])
        mock_npc_service.npc_catalog.get_npc_data = MagicMock(return_value={"es_hostil": True})
        mock_map_manager.can_move_to = MagicMock(return_value=True)

        # Spawnear NPCs (jugador en posición 80,80 que está cerca del área 70-90)
        spawned = await random_spawn_service.spawn_random_npcs_for_player(
            map_id=1, player_x=80, player_y=80
        )

        # Verificar que se spawnearon NPCs
        assert len(spawned) > 0
        assert all(isinstance(npc, NPC) for npc in spawned)

    @pytest.mark.asyncio
    async def test_no_spawn_when_player_far_from_area(
        self,
        random_spawn_service: RandomSpawnService,
        sample_spawn_config: dict,
    ) -> None:
        """Test que no spawneea NPCs cuando jugador está lejos del área."""
        random_spawn_service._random_spawn_configs[1] = [sample_spawn_config]

        # Jugador muy lejos del área (posición 10,10 vs área 70-90)
        spawned = await random_spawn_service.spawn_random_npcs_for_player(
            map_id=1, player_x=10, player_y=10
        )

        # No debe spawnear nada
        assert len(spawned) == 0

    @pytest.mark.asyncio
    async def test_respect_count_limit(
        self,
        random_spawn_service: RandomSpawnService,
        sample_npc: NPC,
        sample_spawn_config: dict,
        mock_npc_service: MagicMock,
        mock_map_manager: MagicMock,
    ) -> None:
        """Test que respeta el límite de count."""
        random_spawn_service._random_spawn_configs[1] = [sample_spawn_config]

        # Simular que ya hay 3 NPCs spawneados en el área
        area_key = RandomSpawnService._get_area_key(sample_spawn_config["area"])
        random_spawn_service._random_spawned_npcs = {
            "instance-1": {"map_id": 1, "area_key": area_key, "spawn_time": time.time()},
            "instance-2": {"map_id": 1, "area_key": area_key, "spawn_time": time.time()},
            "instance-3": {"map_id": 1, "area_key": area_key, "spawn_time": time.time()},
        }

        mock_npc_service.spawn_npc = AsyncMock(return_value=sample_npc)
        mock_npc_service.npc_catalog.get_all_npc_ids = MagicMock(return_value=[1])
        mock_npc_service.npc_catalog.get_npc_data = MagicMock(return_value={"es_hostil": True})
        mock_map_manager.can_move_to = MagicMock(return_value=True)

        # Spawnear (debería spawnear solo 2 más hasta llegar a 5)
        spawned = await random_spawn_service.spawn_random_npcs_for_player(
            map_id=1, player_x=80, player_y=80
        )

        # Debe spawnear solo hasta el límite (2 más para llegar a 5)
        assert len(spawned) <= 2

    @pytest.mark.asyncio
    async def test_respect_cooldown(
        self,
        random_spawn_service: RandomSpawnService,
        sample_spawn_config: dict,
    ) -> None:
        """Test que respeta el cooldown de respawn."""
        random_spawn_service._random_spawn_configs[1] = [sample_spawn_config]

        # Establecer cooldown reciente
        area_key = RandomSpawnService._get_area_key(sample_spawn_config["area"])
        cooldown_key = (1, area_key)
        random_spawn_service._respawn_cooldowns[cooldown_key] = time.time()

        # Intentar spawnear (debería respetar el cooldown)
        spawned = await random_spawn_service.spawn_random_npcs_for_player(
            map_id=1, player_x=80, player_y=80
        )

        # No debe spawnear porque está en cooldown
        assert len(spawned) == 0


class TestOnRandomNPCDeath:
    """Tests para notificación de muerte de NPC random."""

    @pytest.mark.asyncio
    async def test_remove_npc_on_death(
        self, random_spawn_service: RandomSpawnService, sample_npc: NPC
    ) -> None:
        """Test que remueve NPC del tracking cuando muere."""
        # Agregar NPC al tracking
        area_key = "70_70_90_90"
        random_spawn_service._random_spawned_npcs[sample_npc.instance_id] = {
            "map_id": 1,
            "area_key": area_key,
            "spawn_time": time.time(),
        }

        assert sample_npc.instance_id in random_spawn_service._random_spawned_npcs

        # Notificar muerte
        await random_spawn_service.on_random_npc_death(sample_npc.instance_id)

        # Verificar que fue removido
        assert sample_npc.instance_id not in random_spawn_service._random_spawned_npcs

    @pytest.mark.asyncio
    async def test_remove_nonexistent_npc(self, random_spawn_service: RandomSpawnService) -> None:
        """Test que no falla al remover NPC inexistente."""
        # No debe fallar
        await random_spawn_service.on_random_npc_death("nonexistent-instance")


class TestTrySpawnRandomNPC:
    """Tests para intentar spawnear un NPC aleatorio."""

    @pytest.mark.asyncio
    async def test_spawn_success(
        self,
        random_spawn_service: RandomSpawnService,
        sample_npc: NPC,
        sample_spawn_config: dict,
        mock_npc_service: MagicMock,
        mock_map_manager: MagicMock,
    ) -> None:
        """Test spawn exitoso."""
        area = sample_spawn_config["area"]
        area_key = RandomSpawnService._get_area_key(area)

        mock_npc_service.spawn_npc = AsyncMock(return_value=sample_npc)
        mock_npc_service.npc_catalog.get_all_npc_ids = MagicMock(return_value=[1])
        mock_npc_service.npc_catalog.get_npc_data = MagicMock(return_value={"es_hostil": True})
        mock_map_manager.can_move_to = MagicMock(return_value=True)

        npc = await random_spawn_service._try_spawn_random_npc(
            spawn_config=sample_spawn_config,
            map_id=1,
            area=area,
            area_key=area_key,
        )

        assert npc is not None
        assert npc.instance_id == sample_npc.instance_id
        assert sample_npc.instance_id in random_spawn_service._random_spawned_npcs

    @pytest.mark.asyncio
    async def test_spawn_fails_no_free_tiles(
        self,
        random_spawn_service: RandomSpawnService,
        sample_spawn_config: dict,
        mock_map_manager: MagicMock,
    ) -> None:
        """Test que falla cuando no hay tiles libres."""
        area = sample_spawn_config["area"]
        area_key = RandomSpawnService._get_area_key(area)

        # Todos los tiles están ocupados
        mock_map_manager.can_move_to = MagicMock(return_value=False)

        npc = await random_spawn_service._try_spawn_random_npc(
            spawn_config=sample_spawn_config,
            map_id=1,
            area=area,
            area_key=area_key,
        )

        # No debe spawnear NPC
        assert npc is None

    @pytest.mark.asyncio
    async def test_spawn_fails_no_npc_ids(
        self,
        random_spawn_service: RandomSpawnService,
        sample_spawn_config: dict,
        mock_npc_service: MagicMock,
        mock_map_manager: MagicMock,
    ) -> None:
        """Test que falla cuando no hay NPC IDs disponibles."""
        area = sample_spawn_config["area"]
        area_key = RandomSpawnService._get_area_key(area)

        mock_npc_service.npc_catalog.get_all_npc_ids = MagicMock(return_value=[])
        mock_map_manager.can_move_to = MagicMock(return_value=True)

        npc = await random_spawn_service._try_spawn_random_npc(
            spawn_config=sample_spawn_config,
            map_id=1,
            area=area,
            area_key=area_key,
        )

        assert npc is None


class TestSelectRandomNPCId:
    """Tests para seleccionar ID de NPC aleatorio."""

    @pytest.mark.asyncio
    async def test_select_hostile_npc(
        self,
        random_spawn_service: RandomSpawnService,
        mock_npc_service: MagicMock,
    ) -> None:
        """Test seleccionar NPC hostil."""
        mock_npc_service.npc_catalog.get_all_npc_ids = MagicMock(return_value=[1, 2, 3])
        mock_npc_service.npc_catalog.get_npc_data = MagicMock(
            side_effect=lambda npc_id: {"es_hostil": npc_id == 2}
        )

        spawn_config = {"npc_type": "hostile"}
        npc_id = await random_spawn_service._select_random_npc_id(spawn_config)

        assert npc_id is not None
        assert npc_id in {1, 2, 3}

    @pytest.mark.asyncio
    async def test_select_any_npc(
        self,
        random_spawn_service: RandomSpawnService,
        mock_npc_service: MagicMock,
    ) -> None:
        """Test seleccionar cualquier NPC."""
        mock_npc_service.npc_catalog.get_all_npc_ids = MagicMock(return_value=[1, 2, 3])

        spawn_config = {"npc_type": "common"}
        npc_id = await random_spawn_service._select_random_npc_id(spawn_config)

        assert npc_id is not None
        assert npc_id in {1, 2, 3}


class TestAreaHelpers:
    """Tests para funciones helper de áreas."""

    def test_get_area_key(self) -> None:
        """Test generar clave de área."""
        area = {"x1": 70, "y1": 70, "x2": 90, "y2": 90}
        key = RandomSpawnService._get_area_key(area)

        assert key == "70_70_90_90"

    def test_is_player_near_area_close(self) -> None:
        """Test que detecta jugador cerca del área."""
        area = {"x1": 70, "y1": 70, "x2": 90, "y2": 90}
        # Jugador en el centro del área
        is_near = RandomSpawnService._is_player_near_area(80, 80, area, vision_range=15)

        assert is_near is True

    def test_is_player_near_area_far(self) -> None:
        """Test que detecta jugador lejos del área."""
        area = {"x1": 70, "y1": 70, "x2": 90, "y2": 90}
        # Jugador muy lejos
        is_near = RandomSpawnService._is_player_near_area(10, 10, area, vision_range=15)

        assert is_near is False


class TestGetActiveNPCsInArea:
    """Tests para obtener NPCs activos en un área."""

    def test_get_active_npcs(self, random_spawn_service: RandomSpawnService) -> None:
        """Test obtener NPCs activos en un área."""
        area_key = "70_70_90_90"

        # Agregar NPCs al tracking
        random_spawn_service._random_spawned_npcs = {
            "instance-1": {"map_id": 1, "area_key": area_key, "spawn_time": time.time()},
            "instance-2": {"map_id": 1, "area_key": area_key, "spawn_time": time.time()},
            "instance-3": {
                "map_id": 2,
                "area_key": area_key,
                "spawn_time": time.time(),
            },  # Otro mapa
            "instance-4": {
                "map_id": 1,
                "area_key": "100_100_110_110",  # Otra área
                "spawn_time": time.time(),
            },
        }

        active = random_spawn_service._get_active_npcs_in_area(map_id=1, area_key=area_key)

        # Debe retornar solo los NPCs del mapa 1 en el área especificada
        assert len(active) == 2
        assert "instance-1" in active
        assert "instance-2" in active


class TestGetRandomSpawnStatistics:
    """Tests para obtener estadísticas."""

    def test_get_statistics(self, random_spawn_service: RandomSpawnService) -> None:
        """Test obtener estadísticas de random spawns."""
        # Configurar algunos datos
        random_spawn_service._random_spawn_configs[1] = [{"npc_type": "hostile"}]
        random_spawn_service._random_spawned_npcs = {
            "instance-1": {"map_id": 1, "area_key": "key1", "spawn_time": time.time()},
            "instance-2": {"map_id": 1, "area_key": "key2", "spawn_time": time.time()},
        }
        random_spawn_service._respawn_cooldowns[1, "key1"] = time.time()

        stats = random_spawn_service.get_random_spawn_statistics()

        assert stats["total_random_spawned"] == 2
        assert stats["configured_maps"] == 1
        assert stats["active_respawn_cooldowns"] == 1
