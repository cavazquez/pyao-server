"""Tests para el catálogo de NPCs."""

from pathlib import Path

from src.models.npc_catalog import NPCCatalog


class TestNPCCatalog:
    """Tests para NPCCatalog."""

    def test_load_catalog_success(self, tmp_path: Path) -> None:
        """Test de carga exitosa del catálogo."""
        # Crear archivos temporales con NPCs hostiles y amigables
        hostile_file = tmp_path / "npcs_hostiles.toml"
        hostile_file.write_text("""
[[npc]]
id = 1
nombre = "Goblin"
descripcion = "Un goblin salvaje"
body_id = 500
head_id = 0
es_hostil = true
es_atacable = true
nivel = 5
hp_max = 100
oro_min = 10
oro_max = 50
""")

        friendly_file = tmp_path / "npcs_amigables.toml"
        friendly_file.write_text("""
[[npc]]
id = 2
nombre = "Comerciante"
descripcion = "Un comerciante amigable"
body_id = 501
head_id = 1
es_hostil = false
es_atacable = false
nivel = 0
hp_max = 0
oro_min = 0
oro_max = 0
""")

        catalog = NPCCatalog(
            hostile_path=str(hostile_file),
            friendly_path=str(friendly_file),
        )

        # Verificar que se cargaron los NPCs
        assert catalog.npc_exists(1)
        assert catalog.npc_exists(2)
        assert not catalog.npc_exists(999)

        # Verificar datos del Goblin
        goblin = catalog.get_npc_data(1)
        assert goblin is not None
        assert goblin["nombre"] == "Goblin"
        assert goblin["body_id"] == 500
        assert goblin["es_hostil"] is True

        # Verificar datos del Comerciante
        comerciante = catalog.get_npc_data(2)
        assert comerciante is not None
        assert comerciante["nombre"] == "Comerciante"
        assert comerciante["es_hostil"] is False

    def test_get_all_npc_ids(self, tmp_path: Path) -> None:
        """Test de obtención de todos los IDs de NPCs."""
        npc_file = tmp_path / "npcs_hostiles.toml"
        npc_file.write_text("""
[[npc]]
id = 1
nombre = "NPC1"
body_id = 500

[[npc]]
id = 5
nombre = "NPC5"
body_id = 505

[[npc]]
id = 10
nombre = "NPC10"
body_id = 510
""")

        catalog = NPCCatalog(hostile_path=str(npc_file), friendly_path="")
        ids = catalog.get_all_npc_ids()

        assert len(ids) == 3
        assert 1 in ids
        assert 5 in ids
        assert 10 in ids

    def test_get_npc_data_not_found(self, tmp_path: Path) -> None:
        """Test de obtención de NPC inexistente."""
        npc_file = tmp_path / "npcs_hostiles.toml"
        npc_file.write_text("""
[[npc]]
id = 1
nombre = "NPC1"
body_id = 500
""")

        catalog = NPCCatalog(hostile_path=str(npc_file), friendly_path="")
        result = catalog.get_npc_data(999)

        assert result is None

    def test_load_catalog_file_not_found(self) -> None:
        """Test de carga con archivo inexistente."""
        catalog = NPCCatalog(hostile_path="nonexistent.toml", friendly_path="nonexistent2.toml")

        # No debe fallar, solo no cargar NPCs
        assert len(catalog.get_all_npc_ids()) == 0

    def test_load_catalog_no_npc_section(self, tmp_path: Path) -> None:
        """Test de carga con archivo sin sección [npc]."""
        npc_file = tmp_path / "npcs_hostiles.toml"
        npc_file.write_text("""
[other_section]
key = "value"
""")

        catalog = NPCCatalog(hostile_path=str(npc_file), friendly_path="")

        # No debe fallar, solo no cargar NPCs
        assert len(catalog.get_all_npc_ids()) == 0

    def test_load_catalog_npc_without_id(self, tmp_path: Path) -> None:
        """Test de carga con NPC sin ID (debe ignorarse)."""
        npc_file = tmp_path / "npcs_hostiles.toml"
        npc_file.write_text("""
[[npc]]
nombre = "NPC sin ID"
body_id = 500

[[npc]]
id = 2
nombre = "NPC con ID"
body_id = 501
""")

        catalog = NPCCatalog(hostile_path=str(npc_file), friendly_path="")

        # Solo debe cargar el NPC con ID
        assert len(catalog.get_all_npc_ids()) == 1
        assert catalog.npc_exists(2)

    def test_npc_exists(self, tmp_path: Path) -> None:
        """Test de verificación de existencia de NPC."""
        npc_file = tmp_path / "npcs_hostiles.toml"
        npc_file.write_text("""
[[npc]]
id = 1
nombre = "NPC1"
body_id = 500
""")

        catalog = NPCCatalog(hostile_path=str(npc_file), friendly_path="")

        assert catalog.npc_exists(1) is True
        assert catalog.npc_exists(999) is False
