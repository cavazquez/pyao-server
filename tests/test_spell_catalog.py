"""Tests para SpellCatalog."""

from src.spell_catalog import SpellCatalog


class TestSpellCatalog:
    """Tests para el catálogo de hechizos."""

    def test_load_spells(self) -> None:
        """Test de carga de hechizos desde archivo."""
        catalog = SpellCatalog("data/spells.toml")

        # Verificar que se cargó al menos un hechizo
        assert len(catalog.spells) > 0

        # Verificar que existe el Dardo Mágico (ID: 1)
        assert catalog.spell_exists(1)

    def test_get_spell_data(self) -> None:
        """Test de obtener datos de un hechizo."""
        catalog = SpellCatalog("data/spells.toml")

        # Obtener Dardo Mágico
        spell = catalog.get_spell_data(1)
        assert spell is not None
        assert spell["name"] == "Dardo Mágico"
        assert spell["mana_cost"] == 5
        assert spell["min_damage"] == 5
        assert spell["max_damage"] == 15

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
        assert 1 in spell_ids  # Dardo Mágico debe estar

    def test_load_nonexistent_file(self) -> None:
        """Test de cargar archivo inexistente."""
        catalog = SpellCatalog("nonexistent.toml")

        # No debe crashear, solo tener catálogo vacío
        assert len(catalog.spells) == 0
