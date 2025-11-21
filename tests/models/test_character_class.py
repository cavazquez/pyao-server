"""Tests para modelos de clases de personaje."""

from pathlib import Path

import pytest

from src.models.character_class import CharacterClass, ClassCatalog


class TestCharacterClass:
    """Tests para el modelo CharacterClass."""

    def test_character_class_creation(self):
        """Test crear una clase de personaje."""
        character_class = CharacterClass(
            class_id=1,
            name="Mago",
            base_strength=8,
            base_agility=8,
            base_intelligence=15,
            base_charisma=10,
            base_constitution=9,
            allowed_weapon_types=["varita", "baston"],
            allowed_armor_types=["tunica", "capucha"],
            initial_skills={"magia": 10, "robustez": 5},
            description="Maestro de las artes arcanas",
        )

        assert character_class.class_id == 1
        assert character_class.name == "Mago"
        assert character_class.base_strength == 8
        assert character_class.base_intelligence == 15

    def test_base_attributes_property(self):
        """Test que base_attributes retorna diccionario correcto."""
        character_class = CharacterClass(
            class_id=1,
            name="Mago",
            base_strength=8,
            base_agility=8,
            base_intelligence=15,
            base_charisma=10,
            base_constitution=9,
            allowed_weapon_types=[],
            allowed_armor_types=[],
            initial_skills={},
        )

        attrs = character_class.base_attributes
        assert attrs["strength"] == 8
        assert attrs["agility"] == 8
        assert attrs["intelligence"] == 15
        assert attrs["charisma"] == 10
        assert attrs["constitution"] == 9

    def test_can_equip_weapon(self):
        """Test verificación de equipamiento de armas."""
        character_class = CharacterClass(
            class_id=1,
            name="Mago",
            base_strength=8,
            base_agility=8,
            base_intelligence=15,
            base_charisma=10,
            base_constitution=9,
            allowed_weapon_types=["varita", "baston"],
            allowed_armor_types=[],
            initial_skills={},
        )

        assert character_class.can_equip_weapon("varita") is True
        assert character_class.can_equip_weapon("baston") is True
        assert character_class.can_equip_weapon("espada") is False

    def test_can_equip_armor(self):
        """Test verificación de equipamiento de armaduras."""
        character_class = CharacterClass(
            class_id=1,
            name="Mago",
            base_strength=8,
            base_agility=8,
            base_intelligence=15,
            base_charisma=10,
            base_constitution=9,
            allowed_weapon_types=[],
            allowed_armor_types=["tunica", "capucha"],
            initial_skills={},
        )

        assert character_class.can_equip_armor("tunica") is True
        assert character_class.can_equip_armor("capucha") is True
        assert character_class.can_equip_armor("pesada") is False


class TestClassCatalog:
    """Tests para ClassCatalog."""

    @pytest.fixture
    def data_dir(self):
        """Retorna el directorio de datos de test."""
        return Path("data")

    def test_load_classes_from_toml(self, data_dir):
        """Test cargar clases desde archivo TOML."""
        catalog = ClassCatalog(data_dir)

        classes = catalog.get_all_classes()
        assert len(classes) > 0

        # Verificar que se cargaron las clases esperadas
        class_names = [cls.name for cls in classes]
        assert "Mago" in class_names
        assert "Guerrero" in class_names
        assert "Clerigo" in class_names
        assert "Cazador" in class_names

    def test_get_class_by_id(self, data_dir):
        """Test obtener clase por ID."""
        catalog = ClassCatalog(data_dir)

        mago = catalog.get_class(1)
        assert mago is not None
        assert mago.name == "Mago"
        assert mago.class_id == 1

        guerrero = catalog.get_class(3)
        assert guerrero is not None
        assert guerrero.name == "Guerrero"

    def test_get_class_by_name(self, data_dir):
        """Test obtener clase por nombre."""
        catalog = ClassCatalog(data_dir)

        mago = catalog.get_class_by_name("Mago")
        assert mago is not None
        assert mago.class_id == 1

        guerrero = catalog.get_class_by_name("Guerrero")
        assert guerrero is not None
        assert guerrero.class_id == 3

    def test_get_nonexistent_class(self, data_dir):
        """Test obtener clase que no existe."""
        catalog = ClassCatalog(data_dir)

        assert catalog.get_class(999) is None
        assert catalog.get_class_by_name("ClaseInexistente") is None

    def test_class_attributes(self, data_dir):
        """Test que las clases tienen atributos base correctos."""
        catalog = ClassCatalog(data_dir)

        mago = catalog.get_class(1)
        assert mago is not None
        assert mago.base_intelligence == 15  # Mago tiene INT alta
        assert mago.base_strength == 8  # Mago tiene STR baja

        guerrero = catalog.get_class(3)
        assert guerrero is not None
        assert guerrero.base_strength == 15  # Guerrero tiene STR alta
        assert guerrero.base_intelligence == 8  # Guerrero tiene INT baja

    def test_class_initial_skills(self, data_dir):
        """Test que las clases tienen skills iniciales."""
        catalog = ClassCatalog(data_dir)

        mago = catalog.get_class(1)
        assert mago is not None
        assert "magia" in mago.initial_skills
        assert mago.initial_skills["magia"] == 10

        guerrero = catalog.get_class(3)
        assert guerrero is not None
        assert "robustez" in guerrero.initial_skills
        assert guerrero.initial_skills["robustez"] == 10

    def test_has_class(self, data_dir):
        """Test verificar si existe una clase."""
        catalog = ClassCatalog(data_dir)

        assert catalog.has_class(1) is True
        assert catalog.has_class(3) is True
        assert catalog.has_class(10) is True
        assert catalog.has_class(999) is False
