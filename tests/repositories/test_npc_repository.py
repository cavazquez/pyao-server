"""Tests para el repositorio de NPCs."""

from typing import TYPE_CHECKING

import pytest

from src.repositories.npc_repository import NPCRepository

if TYPE_CHECKING:
    from src.utils.redis_client import RedisClient


@pytest.mark.asyncio
class TestNPCRepository:
    """Tests para NPCRepository."""

    async def test_create_npc_instance(self, redis_client: RedisClient) -> None:
        """Test de creación de instancia de NPC."""
        repo = NPCRepository(redis_client)

        npc = await repo.create_npc_instance(
            npc_id=1,
            char_index=10001,
            map_id=1,
            x=50,
            y=50,
            heading=3,
            name="Goblin",
            description="Un goblin salvaje",
            body_id=500,
            head_id=0,
            hp=100,
            max_hp=100,
            level=5,
            is_hostile=True,
            is_attackable=True,
            respawn_time=0,
            respawn_time_max=0,
            gold_min=10,
            gold_max=50,
        )

        assert npc.npc_id == 1
        assert npc.char_index == 10001
        assert npc.name == "Goblin"
        assert npc.map_id == 1
        assert npc.x == 50
        assert npc.y == 50
        assert npc.is_hostile is True
        assert npc.instance_id is not None

    async def test_get_npc(self, redis_client: RedisClient) -> None:
        """Test de obtención de NPC por instance_id."""
        repo = NPCRepository(redis_client)

        # Crear NPC
        created_npc = await repo.create_npc_instance(
            npc_id=2,
            char_index=10002,
            map_id=1,
            x=60,
            y=60,
            heading=1,
            name="Comerciante",
            description="Un comerciante",
            body_id=501,
            head_id=1,
            hp=0,
            max_hp=0,
            level=0,
            is_hostile=False,
            is_attackable=False,
            movement_type="static",
            respawn_time=0,
            respawn_time_max=0,
            gold_min=0,
            gold_max=0,
        )

        # Obtener NPC
        retrieved_npc = await repo.get_npc(created_npc.instance_id)

        assert retrieved_npc is not None
        assert retrieved_npc.instance_id == created_npc.instance_id
        assert retrieved_npc.name == "Comerciante"
        assert retrieved_npc.char_index == 10002

    async def test_get_npc_not_found(self, redis_client: RedisClient) -> None:
        """Test de obtención de NPC inexistente."""
        repo = NPCRepository(redis_client)

        npc = await repo.get_npc("nonexistent-id")

        assert npc is None

    async def test_get_npcs_in_map(self, redis_client: RedisClient) -> None:
        """Test de obtención de NPCs por mapa."""
        repo = NPCRepository(redis_client)

        # Crear NPCs en mapa 1
        await repo.create_npc_instance(
            npc_id=1,
            char_index=10001,
            map_id=1,
            x=50,
            y=50,
            heading=3,
            name="NPC1",
            description="",
            body_id=500,
            head_id=0,
            hp=100,
            max_hp=100,
            level=1,
            is_hostile=False,
            is_attackable=True,
            movement_type="static",
            respawn_time=0,
            respawn_time_max=0,
            gold_min=0,
            gold_max=0,
        )

        await repo.create_npc_instance(
            npc_id=2,
            char_index=10002,
            map_id=1,
            x=60,
            y=60,
            heading=1,
            name="NPC2",
            description="",
            body_id=501,
            head_id=1,
            hp=100,
            max_hp=100,
            level=1,
            is_hostile=False,
            is_attackable=True,
            movement_type="static",
            respawn_time=0,
            respawn_time_max=0,
            gold_min=0,
            gold_max=0,
        )

        # Crear NPC en mapa 2
        await repo.create_npc_instance(
            npc_id=3,
            char_index=10003,
            map_id=2,
            x=70,
            y=70,
            heading=2,
            name="NPC3",
            description="",
            body_id=502,
            head_id=2,
            hp=100,
            max_hp=100,
            level=1,
            is_hostile=False,
            is_attackable=True,
            movement_type="static",
            respawn_time=0,
            respawn_time_max=0,
            gold_min=0,
            gold_max=0,
        )

        # Obtener NPCs del mapa 1
        npcs_map1 = await repo.get_npcs_in_map(1)
        assert len(npcs_map1) == 2

        # Obtener NPCs del mapa 2
        npcs_map2 = await repo.get_npcs_in_map(2)
        assert len(npcs_map2) == 1

        # Obtener NPCs de mapa vacío
        npcs_map3 = await repo.get_npcs_in_map(3)
        assert len(npcs_map3) == 0

    async def test_update_npc_position(self, redis_client: RedisClient) -> None:
        """Test de actualización de posición de NPC."""
        repo = NPCRepository(redis_client)

        # Crear NPC
        npc = await repo.create_npc_instance(
            npc_id=1,
            char_index=10001,
            map_id=1,
            x=50,
            y=50,
            heading=3,
            name="Test NPC",
            description="",
            body_id=500,
            head_id=0,
            hp=100,
            max_hp=100,
            level=1,
            is_hostile=False,
            is_attackable=True,
            movement_type="static",
            respawn_time=0,
            respawn_time_max=0,
            gold_min=0,
            gold_max=0,
        )

        # Actualizar posición
        await repo.update_npc_position(npc.instance_id, 60, 70, 1)

        # Verificar actualización
        updated_npc = await repo.get_npc(npc.instance_id)
        assert updated_npc is not None
        assert updated_npc.x == 60
        assert updated_npc.y == 70
        assert updated_npc.heading == 1

    async def test_remove_npc(self, redis_client: RedisClient) -> None:
        """Test de eliminación de NPC."""
        repo = NPCRepository(redis_client)

        # Crear NPC
        npc = await repo.create_npc_instance(
            npc_id=1,
            char_index=10001,
            map_id=1,
            x=50,
            y=50,
            heading=3,
            name="Test NPC",
            description="",
            body_id=500,
            head_id=0,
            hp=100,
            max_hp=100,
            level=1,
            is_hostile=False,
            is_attackable=True,
            movement_type="static",
            respawn_time=0,
            respawn_time_max=0,
            gold_min=0,
            gold_max=0,
        )

        # Eliminar NPC
        await repo.remove_npc(npc.instance_id)

        # Verificar que no existe
        deleted_npc = await repo.get_npc(npc.instance_id)
        assert deleted_npc is None

        # Verificar que no está en el índice del mapa
        npcs_in_map = await repo.get_npcs_in_map(1)
        assert len(npcs_in_map) == 0

    async def test_clear_all_npcs(self, redis_client: RedisClient) -> None:
        """Test de limpieza de todos los NPCs."""
        repo = NPCRepository(redis_client)

        # Crear varios NPCs
        for i in range(5):
            await repo.create_npc_instance(
                npc_id=i,
                char_index=10000 + i,
                map_id=1,
                x=50 + i,
                y=50 + i,
                heading=3,
                name=f"NPC{i}",
                description="",
                body_id=500 + i,
                head_id=0,
                hp=100,
                max_hp=100,
                level=1,
                is_hostile=False,
                is_attackable=True,
                movement_type="static",
                respawn_time=0,
                respawn_time_max=0,
                gold_min=0,
                gold_max=0,
            )

        # Limpiar todos
        await repo.clear_all_npcs()

        # Verificar que no quedan NPCs
        all_npcs = await repo.get_all_npcs()
        assert len(all_npcs) == 0

    async def test_get_all_npcs(self, redis_client: RedisClient) -> None:
        """Test de obtención de todos los NPCs."""
        repo = NPCRepository(redis_client)

        # Crear NPCs en diferentes mapas
        await repo.create_npc_instance(
            npc_id=1,
            char_index=10001,
            map_id=1,
            x=50,
            y=50,
            heading=3,
            name="NPC1",
            description="",
            body_id=500,
            head_id=0,
            hp=100,
            max_hp=100,
            level=1,
            is_hostile=False,
            is_attackable=True,
            movement_type="static",
            respawn_time=0,
            respawn_time_max=0,
            gold_min=0,
            gold_max=0,
        )

        await repo.create_npc_instance(
            npc_id=2,
            char_index=10002,
            map_id=2,
            x=60,
            y=60,
            heading=1,
            name="NPC2",
            description="",
            body_id=501,
            head_id=1,
            hp=100,
            max_hp=100,
            level=1,
            is_hostile=False,
            is_attackable=True,
            movement_type="static",
            respawn_time=0,
            respawn_time_max=0,
            gold_min=0,
            gold_max=0,
        )

        # Obtener todos
        all_npcs = await repo.get_all_npcs()

        assert len(all_npcs) == 2
        names = {npc.name for npc in all_npcs}
        assert "NPC1" in names
        assert "NPC2" in names

    async def test_update_npc_hp(self, redis_client: RedisClient) -> None:
        """Test de actualización de HP de NPC."""
        repo = NPCRepository(redis_client)

        # Crear NPC
        npc = await repo.create_npc_instance(
            npc_id=1,
            char_index=10001,
            map_id=1,
            x=50,
            y=50,
            heading=3,
            name="Test NPC",
            description="",
            body_id=500,
            head_id=0,
            hp=100,
            max_hp=100,
            level=1,
            is_hostile=True,
            is_attackable=True,
            movement_type="static",
            respawn_time=0,
            respawn_time_max=0,
            gold_min=0,
            gold_max=0,
        )

        # Actualizar HP
        await repo.update_npc_hp(npc.instance_id, 50)

        # Verificar actualización
        updated_npc = await repo.get_npc(npc.instance_id)
        assert updated_npc is not None
        assert updated_npc.hp == 50

    async def test_remove_npc_not_found(self, redis_client: RedisClient) -> None:
        """Test de eliminación de NPC inexistente."""
        repo = NPCRepository(redis_client)

        # Intentar eliminar NPC que no existe (no debería lanzar error)
        await repo.remove_npc("nonexistent-id")
