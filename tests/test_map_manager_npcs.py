"""Tests para gestión de NPCs en MapManager."""

from src.map_manager import MapManager
from src.npc import NPC


class TestMapManagerNPCs:
    """Tests para gestión de NPCs en MapManager."""

    def test_add_npc(self) -> None:
        """Test de agregar NPC a un mapa."""
        manager = MapManager()

        npc = NPC(
            npc_id=1,
            char_index=10001,
            instance_id="test-id-1",
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
            movement_type="static",
            respawn_time=0,
            gold_min=10,
            gold_max=50,
        )

        manager.add_npc(1, npc)

        # Verificar que se agregó
        npcs = manager.get_npcs_in_map(1)
        assert len(npcs) == 1
        assert npcs[0].name == "Goblin"

    def test_remove_npc(self) -> None:
        """Test de remover NPC de un mapa."""
        manager = MapManager()

        npc = NPC(
            npc_id=1,
            char_index=10001,
            instance_id="test-id-1",
            map_id=1,
            x=50,
            y=50,
            heading=3,
            name="Goblin",
            description="",
            body_id=500,
            head_id=0,
            hp=100,
            max_hp=100,
            level=5,
            is_hostile=True,
            is_attackable=True,
            movement_type="static",
            respawn_time=0,
            gold_min=10,
            gold_max=50,
        )

        manager.add_npc(1, npc)
        manager.remove_npc(1, "test-id-1")

        # Verificar que se removió
        npcs = manager.get_npcs_in_map(1)
        assert len(npcs) == 0

    def test_get_npcs_in_map_empty(self) -> None:
        """Test de obtener NPCs de mapa vacío."""
        manager = MapManager()

        npcs = manager.get_npcs_in_map(1)

        assert len(npcs) == 0

    def test_get_npcs_in_map_multiple(self) -> None:
        """Test de obtener múltiples NPCs de un mapa."""
        manager = MapManager()

        # Agregar varios NPCs
        for i in range(3):
            npc = NPC(
                npc_id=i,
                char_index=10000 + i,
                instance_id=f"test-id-{i}",
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
                gold_min=0,
                gold_max=0,
            )
            manager.add_npc(1, npc)

        npcs = manager.get_npcs_in_map(1)

        assert len(npcs) == 3
        names = {npc.name for npc in npcs}
        assert "NPC0" in names
        assert "NPC1" in names
        assert "NPC2" in names

    def test_get_npc_by_char_index(self) -> None:
        """Test de obtener NPC por CharIndex."""
        manager = MapManager()

        npc = NPC(
            npc_id=1,
            char_index=10001,
            instance_id="test-id-1",
            map_id=1,
            x=50,
            y=50,
            heading=3,
            name="Goblin",
            description="",
            body_id=500,
            head_id=0,
            hp=100,
            max_hp=100,
            level=5,
            is_hostile=True,
            is_attackable=True,
            movement_type="static",
            respawn_time=0,
            gold_min=10,
            gold_max=50,
        )

        manager.add_npc(1, npc)

        # Buscar por CharIndex
        found_npc = manager.get_npc_by_char_index(1, 10001)

        assert found_npc is not None
        assert found_npc.name == "Goblin"
        assert found_npc.char_index == 10001

    def test_get_npc_by_char_index_not_found(self) -> None:
        """Test de buscar NPC por CharIndex inexistente."""
        manager = MapManager()

        found_npc = manager.get_npc_by_char_index(1, 99999)

        assert found_npc is None

    def test_get_all_npcs(self) -> None:
        """Test de obtener todos los NPCs del mundo."""
        manager = MapManager()

        # Agregar NPCs en diferentes mapas
        for map_id in [1, 2]:
            for i in range(2):
                npc = NPC(
                    npc_id=i,
                    char_index=10000 + map_id * 100 + i,
                    instance_id=f"test-id-{map_id}-{i}",
                    map_id=map_id,
                    x=50,
                    y=50,
                    heading=3,
                    name=f"NPC-Map{map_id}-{i}",
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
                    gold_min=0,
                    gold_max=0,
                )
                manager.add_npc(map_id, npc)

        all_npcs = manager.get_all_npcs()

        assert len(all_npcs) == 4

    def test_npcs_isolated_by_map(self) -> None:
        """Test de que los NPCs están aislados por mapa."""
        manager = MapManager()

        # Agregar NPC en mapa 1
        npc1 = NPC(
            npc_id=1,
            char_index=10001,
            instance_id="test-id-1",
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
            gold_min=0,
            gold_max=0,
        )
        manager.add_npc(1, npc1)

        # Agregar NPC en mapa 2
        npc2 = NPC(
            npc_id=2,
            char_index=10002,
            instance_id="test-id-2",
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
            gold_min=0,
            gold_max=0,
        )
        manager.add_npc(2, npc2)

        # Verificar aislamiento
        npcs_map1 = manager.get_npcs_in_map(1)
        npcs_map2 = manager.get_npcs_in_map(2)

        assert len(npcs_map1) == 1
        assert len(npcs_map2) == 1
        assert npcs_map1[0].name == "NPC1"
        assert npcs_map2[0].name == "NPC2"
