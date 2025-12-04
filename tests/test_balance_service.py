"""Tests para el BalanceService.

Verifica que los datos de balance se carguen correctamente
y que los cálculos de modificadores funcionen como esperan.
"""

import shutil
import sys
import tempfile
from pathlib import Path

# Agregar src al path para poder importar servicios
sys.path.append(str(Path(__file__).parent.parent / "src"))

from services.game.balance_service import BalanceService


class TestBalanceService:
    """Tests para BalanceService."""

    def setup_method(self):
        """Configuración para cada test."""
        # Crear directorio temporal con estructura classes/
        self.temp_dir = Path(tempfile.mkdtemp())
        classes_dir = self.temp_dir / "classes"
        classes_dir.mkdir(parents=True, exist_ok=True)
        self.balance_file = classes_dir / "balance.toml"

        # Datos de prueba
        test_balance_data = """# Modificadores de atributos por raza
[racial_modifiers]
[[racial_modifiers.races]]
name = "Humano"
strength = 1
agility = 1
intelligence = 0
charisma = 0
constitution = 2

[[racial_modifiers.races]]
name = "Elfo"
strength = -1
agility = 3
intelligence = 2
charisma = 2
constitution = 1

# Modificadores de combate por clase
[class_modifiers]
[[class_modifiers.classes]]
name = "Guerrero"
evasion = 1.0
ataquearmas = 1.0
danoarmas = 1.1
vida = 1.2

[[class_modifiers.classes]]
name = "Mago"
evasion = 0.4
ataquearmas = 0.7
danoarmas = 0.5
vida = 0.8
"""

        self.balance_file.write_text(test_balance_data, encoding="utf-8")
        self.service = BalanceService(self.temp_dir)

    def teardown_method(self):
        """Limpieza después de cada test."""
        # Eliminar archivos temporales
        shutil.rmtree(self.temp_dir)

    def test_load_racial_modifiers(self):
        """Test que los modificadores raciales se cargan correctamente."""
        assert self.service.get_racial_modifier("Humano", "strength") == 1
        assert self.service.get_racial_modifier("Humano", "constitution") == 2
        assert self.service.get_racial_modifier("Elfo", "strength") == -1
        assert self.service.get_racial_modifier("Elfo", "agility") == 3
        assert self.service.get_racial_modifier("Inexistente", "strength") == 0

    def test_load_class_modifiers(self):
        """Test que los modificadores de clase se cargan correctamente."""
        assert self.service.get_class_modifier("Guerrero", "danoarmas") == 1.1
        assert self.service.get_class_modifier("Guerrero", "vida") == 1.2
        assert self.service.get_class_modifier("Mago", "evasion") == 0.4
        assert self.service.get_class_modifier("Mago", "danoarmas") == 0.5
        assert self.service.get_class_modifier("Inexistente", "danoarmas") == 1.0

    def test_apply_racial_modifiers(self):
        """Test que se aplican correctamente los modificadores raciales."""
        base_stats = {
            "strength": 10,
            "agility": 10,
            "intelligence": 10,
            "charisma": 10,
            "constitution": 10,
        }

        human_stats = self.service.apply_racial_modifiers(base_stats, "Humano")
        expected_human = {
            "strength": 11,  # 10 + 1
            "agility": 11,  # 10 + 1
            "intelligence": 10,  # 10 + 0
            "charisma": 10,  # 10 + 0
            "constitution": 12,  # 10 + 2
        }
        assert human_stats == expected_human

        elf_stats = self.service.apply_racial_modifiers(base_stats, "Elfo")
        expected_elf = {
            "strength": 9,  # 10 - 1
            "agility": 13,  # 10 + 3
            "intelligence": 12,  # 10 + 2
            "charisma": 12,  # 10 + 2
            "constitution": 11,  # 10 + 1
        }
        assert elf_stats == expected_elf

    def test_calculate_damage(self):
        """Test cálculo de daño con modificadores de clase."""
        base_damage = 100

        warrior_damage = self.service.calculate_damage(base_damage, "Guerrero")
        assert warrior_damage == 110  # 100 * 1.1

        mage_damage = self.service.calculate_damage(base_damage, "Mago")
        assert mage_damage == 50  # 100 * 0.5

        # Clase inexistente debería retornar daño base
        unknown_damage = self.service.calculate_damage(base_damage, "Inexistente")
        assert unknown_damage == base_damage

    def test_calculate_evasion(self):
        """Test cálculo de evasión con modificadores de clase."""
        base_evasion = 50

        warrior_evasion = self.service.calculate_evasion(base_evasion, "Guerrero")
        assert warrior_evasion == 50  # 50 * 1.0

        mage_evasion = self.service.calculate_evasion(base_evasion, "Mago")
        assert mage_evasion == 20  # 50 * 0.4

    def test_calculate_max_health(self):
        """Test cálculo de salud máxima con modificadores de clase."""
        base_health = 100

        warrior_health = self.service.calculate_max_health(base_health, "Guerrero")
        assert warrior_health == 120  # 100 * 1.2

        mage_health = self.service.calculate_max_health(base_health, "Mago")
        assert mage_health == 80  # 100 * 0.8

    def test_get_available_races(self):
        """Test obtener lista de razas disponibles."""
        races = self.service.get_available_races()
        assert "Humano" in races
        assert "Elfo" in races
        assert len(races) == 2

    def test_get_available_classes(self):
        """Test obtener lista de clases disponibles."""
        classes = self.service.get_available_classes()
        assert "Guerrero" in classes
        assert "Mago" in classes
        assert len(classes) == 2

    def test_validate_race_and_class(self):
        """Test validación de razas y clases."""
        assert self.service.validate_race("Humano") is True
        assert self.service.validate_race("Inexistente") is False
        assert self.service.validate_class("Guerrero") is True
        assert self.service.validate_class("Inexistente") is False

    def test_missing_balance_file(self):
        """Test comportamiento cuando no existe el archivo de balance."""
        empty_dir = Path(tempfile.mkdtemp())
        try:
            service = BalanceService(empty_dir)
            # No debería cargar nada
            assert len(service.get_available_races()) == 0
            assert len(service.get_available_classes()) == 0
        finally:
            shutil.rmtree(empty_dir)

    def test_integration_with_real_data(self):
        """Test de integración con datos reales del cliente."""
        # Usar los datos reales si existen
        real_balance_file = Path("data/classes/balance.toml")
        if real_balance_file.exists():
            real_service = BalanceService(Path("data"))

            # Verificar que cargue datos reales
            assert len(real_service.get_available_races()) > 0
            assert len(real_service.get_available_classes()) > 0

            # Verificar datos específicos del cliente
            assert real_service.get_racial_modifier("Humano", "strength") == 1
            assert real_service.get_racial_modifier("Elfo", "agility") == 3
            assert "Guerrero" in real_service.get_available_classes()
            assert "Mago" in real_service.get_available_classes()
