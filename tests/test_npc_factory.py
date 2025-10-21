"""Tests para NPCFactory."""


from src.npc import NPC
from src.npc_factory import NPCFactory


class TestNPCFactory:
    """Tests para el factory de NPCs."""

    def test_create_hostile_with_minimal_params(self) -> None:
        """Test de creación de NPC hostil con parámetros mínimos."""
        npc = NPCFactory.create_hostile(
            npc_id=1,
            name="Test NPC",
            body_id=10,
            hp=100,
            level=5,
            x=50,
            y=50,
            map_id=1,
            char_index=10001,
        )

        assert isinstance(npc, NPC)
        assert npc.npc_id == 1
        assert npc.name == "Test NPC"
        assert npc.body_id == 10
        assert npc.hp == 100
        assert npc.max_hp == 100
        assert npc.level == 5
        assert npc.x == 50
        assert npc.y == 50
        assert npc.map_id == 1
        assert npc.char_index == 10001
        assert npc.is_hostile is True
        assert npc.is_attackable is True
        assert npc.is_merchant is False
        assert npc.is_banker is False

    def test_create_hostile_with_full_params(self) -> None:
        """Test de creación de NPC hostil con todos los parámetros."""
        npc = NPCFactory.create_hostile(
            npc_id=1,
            name="Goblin Boss",
            body_id=14,
            hp=500,
            level=10,
            x=75,
            y=80,
            map_id=5,
            char_index=10005,
            heading=2,
            head_id=0,
            description="Un goblin jefe poderoso",
            respawn_time=120,
            respawn_time_max=240,
            gold_min=50,
            gold_max=200,
            attack_damage=25,
            attack_cooldown=2.0,
            aggro_range=12,
            fx=5,
            fx_loop=15,
        )

        assert npc.name == "Goblin Boss"
        assert npc.description == "Un goblin jefe poderoso"
        assert npc.heading == 2
        assert npc.head_id == 0
        assert npc.respawn_time == 120
        assert npc.respawn_time_max == 240
        assert npc.gold_min == 50
        assert npc.gold_max == 200
        assert npc.attack_damage == 25
        assert npc.attack_cooldown == 2.0
        assert npc.aggro_range == 12
        assert npc.fx == 5
        assert npc.fx_loop == 15

    def test_create_hostile_default_values(self) -> None:
        """Test de que los valores por defecto sean correctos."""
        npc = NPCFactory.create_hostile(
            npc_id=1,
            name="Default NPC",
            body_id=1,
            hp=50,
            level=1,
            x=10,
            y=10,
            map_id=1,
            char_index=10001,
        )

        # Verificar valores por defecto
        assert npc.heading == 3  # Sur por defecto
        assert npc.head_id == 0  # Sin cabeza
        assert npc.description == ""
        assert npc.respawn_time == 60
        assert npc.respawn_time_max == 120
        assert npc.gold_min == 5
        assert npc.gold_max == 20
        assert npc.attack_damage == 10
        assert npc.attack_cooldown == 3.0
        assert npc.aggro_range == 8
        assert npc.fx == 0
        assert npc.fx_loop == 0
        assert npc.movement_type == "random"

    def test_create_hostile_instance_id_is_unique(self) -> None:
        """Test de que cada NPC tiene un instance_id único."""
        npc1 = NPCFactory.create_hostile(
            npc_id=1,
            name="NPC 1",
            body_id=1,
            hp=100,
            level=5,
            x=10,
            y=10,
            map_id=1,
            char_index=10001,
        )

        npc2 = NPCFactory.create_hostile(
            npc_id=1,
            name="NPC 2",
            body_id=1,
            hp=100,
            level=5,
            x=20,
            y=20,
            map_id=1,
            char_index=10002,
        )

        assert npc1.instance_id != npc2.instance_id
        assert len(npc1.instance_id) > 0
        assert len(npc2.instance_id) > 0

    def test_create_hostile_with_combat_params(self) -> None:
        """Test de creación con parámetros de combate específicos."""
        # NPC rápido y débil
        fast_npc = NPCFactory.create_hostile(
            npc_id=1,
            name="Fast",
            body_id=1,
            hp=50,
            level=3,
            x=10,
            y=10,
            map_id=1,
            char_index=10001,
            attack_damage=5,
            attack_cooldown=1.0,
            aggro_range=5,
        )

        # NPC lento y fuerte
        strong_npc = NPCFactory.create_hostile(
            npc_id=2,
            name="Strong",
            body_id=2,
            hp=500,
            level=20,
            x=20,
            y=20,
            map_id=1,
            char_index=10002,
            attack_damage=100,
            attack_cooldown=5.0,
            aggro_range=15,
        )

        assert fast_npc.attack_damage == 5
        assert fast_npc.attack_cooldown == 1.0
        assert fast_npc.aggro_range == 5

        assert strong_npc.attack_damage == 100
        assert strong_npc.attack_cooldown == 5.0
        assert strong_npc.aggro_range == 15

    def test_create_hostile_with_fx_effects(self) -> None:
        """Test de creación con efectos visuales."""
        npc = NPCFactory.create_hostile(
            npc_id=8,
            name="Araña Gigante",
            body_id=42,
            hp=1000,
            level=8,
            x=50,
            y=50,
            map_id=1,
            char_index=10007,
            fx=10,  # Veneno al morir
            fx_loop=15,  # Aura venenosa
        )

        assert npc.fx == 10
        assert npc.fx_loop == 15

    def test_create_friendly_with_minimal_params(self) -> None:
        """Test de creación de NPC amigable con parámetros mínimos."""
        npc = NPCFactory.create_friendly(
            npc_id=2,
            name="Comerciante",
            body_id=501,
            x=30,
            y=30,
            map_id=1,
            char_index=10001,
        )

        assert isinstance(npc, NPC)
        assert npc.npc_id == 2
        assert npc.name == "Comerciante"
        assert npc.body_id == 501
        assert npc.is_hostile is False
        assert npc.is_attackable is False
        assert npc.is_merchant is False
        assert npc.is_banker is False
        assert npc.movement_type == "static"
        assert npc.respawn_time == 0
        assert npc.respawn_time_max == 0

    def test_create_friendly_merchant(self) -> None:
        """Test de creación de NPC mercader."""
        npc = NPCFactory.create_friendly(
            npc_id=2,
            name="Comerciante",
            body_id=501,
            x=50,
            y=50,
            map_id=1,
            char_index=10001,
            is_merchant=True,
        )

        assert npc.is_merchant is True
        assert npc.is_banker is False

    def test_create_friendly_banker(self) -> None:
        """Test de creación de NPC banquero."""
        npc = NPCFactory.create_friendly(
            npc_id=5,
            name="Banquero",
            body_id=504,
            x=50,
            y=44,
            map_id=1,
            char_index=10002,
            is_banker=True,
        )

        assert npc.is_banker is True
        assert npc.is_merchant is False

    def test_create_friendly_default_values(self) -> None:
        """Test de valores por defecto para NPCs amigables."""
        npc = NPCFactory.create_friendly(
            npc_id=3,
            name="Guardia",
            body_id=502,
            x=40,
            y=40,
            map_id=1,
            char_index=10003,
        )

        assert npc.heading == 3  # Sur por defecto
        assert npc.head_id == 1  # Con cabeza por defecto
        assert npc.description == ""
        assert npc.hp == 100
        assert npc.max_hp == 100
        assert npc.level == 1
        assert npc.gold_min == 0
        assert npc.gold_max == 0

    def test_create_goblin_helper(self) -> None:
        """Test del método helper create_goblin."""
        npc = NPCFactory.create_goblin(x=50, y=50, map_id=1, char_index=10001)

        assert npc.npc_id == 1
        assert npc.name == "Goblin"
        assert npc.body_id == 14
        assert npc.hp == 110
        assert npc.level == 5
        assert npc.is_hostile is True
        assert npc.attack_damage == 8
        assert npc.attack_cooldown == 2.5
        assert npc.aggro_range == 6
        assert npc.fx == 5

    def test_create_lobo_helper(self) -> None:
        """Test del método helper create_lobo."""
        npc = NPCFactory.create_lobo(x=60, y=60, map_id=1, char_index=10002)

        assert npc.npc_id == 7
        assert npc.name == "Lobo"
        assert npc.body_id == 10
        assert npc.hp == 80
        assert npc.level == 3
        assert npc.fx == 5

    def test_create_arana_helper(self) -> None:
        """Test del método helper create_arana."""
        npc = NPCFactory.create_arana(x=70, y=70, map_id=1, char_index=10003)

        assert npc.npc_id == 8
        assert npc.name == "Araña Gigante"
        assert npc.body_id == 42
        assert npc.hp == 150
        assert npc.level == 8
        assert npc.fx == 10  # Veneno
        assert npc.fx_loop == 15  # Aura venenosa

    def test_create_comerciante_helper(self) -> None:
        """Test del método helper create_comerciante."""
        npc = NPCFactory.create_comerciante(x=30, y=30, map_id=1, char_index=10001)

        assert npc.npc_id == 2
        assert npc.name == "Comerciante"
        assert npc.body_id == 501
        assert npc.is_merchant is True
        assert npc.is_hostile is False

    def test_create_banquero_helper(self) -> None:
        """Test del método helper create_banquero."""
        npc = NPCFactory.create_banquero(x=50, y=44, map_id=1, char_index=10002)

        assert npc.npc_id == 5
        assert npc.name == "Banquero"
        assert npc.body_id == 504
        assert npc.is_banker is True
        assert npc.is_hostile is False

    def test_hostile_npc_always_has_is_hostile_true(self) -> None:
        """Test de que los NPCs hostiles siempre tienen is_hostile=True."""
        npc = NPCFactory.create_hostile(
            npc_id=1,
            name="Test",
            body_id=1,
            hp=100,
            level=5,
            x=10,
            y=10,
            map_id=1,
            char_index=10001,
        )

        # No importa qué parámetros pases, siempre debe ser hostil
        assert npc.is_hostile is True
        assert npc.is_attackable is True

    def test_friendly_npc_always_has_is_hostile_false(self) -> None:
        """Test de que los NPCs amigables siempre tienen is_hostile=False."""
        npc = NPCFactory.create_friendly(
            npc_id=2,
            name="Test",
            body_id=501,
            x=10,
            y=10,
            map_id=1,
            char_index=10001,
        )

        # No importa qué parámetros pases, siempre debe ser amigable
        assert npc.is_hostile is False
        assert npc.is_attackable is False
