"""Tests básicos para LootTableService."""

from src.loot_table_service import LootTableService


class TestLootTableService:
    """Tests básicos para LootTableService."""

    def test_init(self) -> None:
        """Test de inicialización."""
        service = LootTableService()

        assert service is not None

    def test_get_loot_for_npc_not_found(self) -> None:
        """Test de obtención de loot para NPC no encontrado."""
        service = LootTableService()

        # NPC que no existe
        loot = service.get_loot_for_npc(npc_id=99999)

        assert loot == []
