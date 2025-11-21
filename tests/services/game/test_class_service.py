"""Tests para ClassService."""

from pathlib import Path

import pytest

from src.services.game.class_service import ClassService


@pytest.fixture
def class_service():
    """Crea una instancia de ClassService."""
    return ClassService(Path("data"))


class TestClassService:
    """Tests para ClassService."""

    def test_get_class(self, class_service):
        """Test obtener clase por ID."""
        mago = class_service.get_class(1)
        assert mago is not None
        assert mago.name == "Mago"

        assert class_service.get_class(999) is None

    def test_get_class_by_name(self, class_service):
        """Test obtener clase por nombre."""
        guerrero = class_service.get_class_by_name("Guerrero")
        assert guerrero is not None
        assert guerrero.class_id == 3

        assert class_service.get_class_by_name("ClaseInexistente") is None

    def test_get_all_classes(self, class_service):
        """Test obtener todas las clases."""
        classes = class_service.get_all_classes()
        assert len(classes) >= 4  # Al menos las 4 clases básicas

        class_names = [cls.name for cls in classes]
        assert "Mago" in class_names
        assert "Guerrero" in class_names

    def test_get_base_attributes(self, class_service):
        """Test obtener atributos base de una clase."""
        attrs = class_service.get_base_attributes(1)  # Mago
        assert attrs["intelligence"] == 15
        assert attrs["strength"] == 8

        attrs = class_service.get_base_attributes(3)  # Guerrero
        assert attrs["strength"] == 15
        assert attrs["intelligence"] == 8

    def test_get_base_attributes_nonexistent_class(self, class_service):
        """Test obtener atributos base de clase inexistente (valores por defecto)."""
        attrs = class_service.get_base_attributes(999)
        assert attrs["strength"] == 10
        assert attrs["agility"] == 10
        assert attrs["intelligence"] == 10

    def test_apply_class_base_attributes(self, class_service):
        """Test aplicar atributos base de clase a atributos de dados."""
        dice_attributes = {
            "strength": 10,
            "agility": 10,
            "intelligence": 10,
            "charisma": 10,
            "constitution": 10,
        }

        # Mago: base INT=15, STR=8
        final_attrs = class_service.apply_class_base_attributes(dice_attributes, 1)
        assert final_attrs["intelligence"] == 25  # 10 (dados) + 15 (base clase)
        assert final_attrs["strength"] == 18  # 10 (dados) + 8 (base clase)

        # Guerrero: base STR=15, INT=8
        final_attrs = class_service.apply_class_base_attributes(dice_attributes, 3)
        assert final_attrs["strength"] == 25  # 10 (dados) + 15 (base clase)
        assert final_attrs["intelligence"] == 18  # 10 (dados) + 8 (base clase)

    def test_get_initial_skills(self, class_service):
        """Test obtener skills iniciales de una clase."""
        skills = class_service.get_initial_skills(1)  # Mago
        assert "magia" in skills
        assert skills["magia"] == 10

        skills = class_service.get_initial_skills(3)  # Guerrero
        assert "robustez" in skills
        assert skills["robustez"] == 10

    def test_get_initial_skills_nonexistent_class(self, class_service):
        """Test obtener skills de clase inexistente (vacío)."""
        skills = class_service.get_initial_skills(999)
        assert skills == {}

    def test_can_equip_weapon(self, class_service):
        """Test verificar si clase puede equipar arma (método existe pero no se usa)."""
        # Mago puede equipar varita según definición
        assert class_service.can_equip_weapon(1, "varita") is True
        assert class_service.can_equip_weapon(1, "espada") is False

        # Guerrero puede equipar espada
        assert class_service.can_equip_weapon(3, "espada") is True
        assert class_service.can_equip_weapon(3, "varita") is False

    def test_can_equip_armor(self, class_service):
        """Test verificar si clase puede equipar armadura (método existe pero no se usa)."""
        # Mago puede equipar túnica
        assert class_service.can_equip_armor(1, "tunica") is True
        assert class_service.can_equip_armor(1, "pesada") is False

        # Guerrero puede equipar armadura pesada
        assert class_service.can_equip_armor(3, "pesada") is True
        assert class_service.can_equip_armor(3, "tunica") is False

    def test_validate_class(self, class_service):
        """Test validar si una clase existe."""
        assert class_service.validate_class(1) is True
        assert class_service.validate_class(3) is True
        assert class_service.validate_class(10) is True
        assert class_service.validate_class(999) is False
