"""Tests para LootTableService."""

from src.loot_table_service import LootTableService


class TestLootTableService:
    """Tests para LootTableService."""

    def test_init(self) -> None:
        """Test de inicialización."""
        service = LootTableService()
        assert service is not None

    def test_loads_loot_tables_from_file(self) -> None:
        """Test que verifica que se cargan las loot tables desde el archivo."""
        service = LootTableService()

        # Verificar que se cargaron loot tables
        # Deberían existir al menos los NPCs configurados
        assert service.has_loot_table(1)  # Goblin
        assert service.has_loot_table(4)  # Orco
        assert service.has_loot_table(7)  # Lobo

    def test_get_loot_for_npc_not_found(self) -> None:
        """Test de obtención de loot para NPC no encontrado."""
        service = LootTableService()

        # NPC que no existe
        loot = service.get_loot_for_npc(npc_id=99999)
        assert loot == []

    def test_get_loot_for_goblin(self) -> None:
        """Test de obtención de loot para Goblin."""
        service = LootTableService()

        # Goblin siempre dropea oro (probability=1.0)
        loot = service.get_loot_for_npc(npc_id=1)

        # Debe retornar una lista (puede estar vacía si la probabilidad falla)
        assert isinstance(loot, list)

        # Si hay loot, debe ser tuplas (item_id, quantity)
        for item_id, quantity in loot:
            assert isinstance(item_id, int)
            assert isinstance(quantity, int)
            assert quantity > 0

    def test_get_loot_table(self) -> None:
        """Test de obtención de loot table."""
        service = LootTableService()

        # Obtener loot table de Goblin
        loot_table = service.get_loot_table(npc_id=1)

        assert loot_table is not None
        assert loot_table.npc_id == 1
        assert loot_table.name == "Goblin"
        assert len(loot_table.items) > 0

    def test_has_loot_table(self) -> None:
        """Test de verificación de existencia de loot table."""
        service = LootTableService()

        # NPCs que deberían tener loot table
        assert service.has_loot_table(1) is True  # Goblin
        assert service.has_loot_table(4) is True  # Orco
        assert service.has_loot_table(7) is True  # Lobo
        assert service.has_loot_table(8) is True  # Araña
        assert service.has_loot_table(9) is True  # Serpiente
        assert service.has_loot_table(10) is True  # Dragón
        assert service.has_loot_table(11) is True  # Esqueleto
        assert service.has_loot_table(12) is True  # Zombie
        assert service.has_loot_table(13) is True  # Troll
        assert service.has_loot_table(14) is True  # Ogro

        # NPC que no existe
        assert service.has_loot_table(99999) is False

    def test_loot_items_have_valid_quantities(self) -> None:
        """Test que verifica que las cantidades de loot son válidas."""
        service = LootTableService()

        # Generar loot múltiples veces para verificar rangos
        for _ in range(10):
            loot = service.get_loot_for_npc(npc_id=1)  # Goblin

            for _item_id, quantity in loot:
                # Verificar que la cantidad es positiva
                assert quantity > 0
                # Verificar que no es excesiva (max configurado es 1000 para dragón)
                assert quantity <= 1000

    def test_dragon_boss_loot(self) -> None:
        """Test de loot del Dragón (boss)."""
        service = LootTableService()

        # Verificar que el Dragón tiene loot table
        assert service.has_loot_table(10) is True

        loot_table = service.get_loot_table(10)
        assert loot_table is not None
        assert loot_table.name == "Dragón"

        # El Dragón debe tener varios items configurados
        assert len(loot_table.items) >= 5
