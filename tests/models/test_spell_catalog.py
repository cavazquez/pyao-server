"""Tests para SpellCatalog."""

from src.models.spell_catalog import SpellCatalog


class TestSpellCatalog:
    """Tests para el catálogo de hechizos."""

    def test_load_spells(self) -> None:
        """Test de carga de hechizos desde archivo."""
        catalog = SpellCatalog("data/spells.toml")

        # Verificar que se cargó al menos un hechizo
        assert len(catalog.spells) > 0

        # Verificar que existe el Antídoto Mágico (ID: 1) y Dardo Mágico (ID: 2)
        assert catalog.spell_exists(1)  # Antídoto Mágico
        assert catalog.spell_exists(2)  # Dardo Mágico

    def test_get_spell_data(self) -> None:
        """Test de obtener datos de un hechizo."""
        catalog = SpellCatalog("data/spells.toml")

        # Obtener Antídoto Mágico (ID: 1 según archivo original)
        spell = catalog.get_spell_data(1)
        assert spell is not None
        assert spell["name"] == "Antídoto Mágico"
        assert spell["mana_cost"] == 12
        assert spell["min_damage"] == 0
        assert spell["max_damage"] == 0

        # Verificar Dardo Mágico (ID: 2 según archivo original)
        spell2 = catalog.get_spell_data(2)
        assert spell2 is not None
        assert spell2["name"] == "Dardo Mágico"
        assert spell2["mana_cost"] == 10
        assert spell2["min_damage"] == 2
        assert spell2["max_damage"] == 5

    def test_spell_not_exists(self) -> None:
        """Test de hechizo inexistente."""
        catalog = SpellCatalog("data/spells.toml")

        # Verificar que un hechizo inexistente retorna False
        assert not catalog.spell_exists(999)

        # Verificar que get_spell_data retorna None
        assert catalog.get_spell_data(999) is None

    def test_get_all_spell_ids(self) -> None:
        """Test de obtener todos los IDs de hechizos."""
        catalog = SpellCatalog("data/spells.toml")

        spell_ids = catalog.get_all_spell_ids()
        assert isinstance(spell_ids, list)
        assert 1 in spell_ids  # Antídoto Mágico debe estar
        assert 2 in spell_ids  # Dardo Mágico debe estar

    def test_load_nonexistent_file(self) -> None:
        """Test de cargar archivo inexistente."""
        catalog = SpellCatalog("nonexistent.toml")

        # No debe crashear, solo tener catálogo vacío
        assert len(catalog.spells) == 0
