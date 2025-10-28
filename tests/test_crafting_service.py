"""Tests para el CraftingService.

Verifica que las recetas de crafting se carguen correctamente
y que el sistema de crafting funcione como esperan.
"""

import random
import shutil
import sys
import tempfile
from pathlib import Path

# Agregar src al path para poder importar servicios
sys.path.append(str(Path(__file__).parent.parent / "src"))

from services.game.crafting_service import CraftingService


class TestCraftingService:
    """Tests para CraftingService."""

    def setup_method(self):
        """Configuración para cada test."""
        # Crear directorio temporal con datos de crafting
        self.temp_dir = Path(tempfile.mkdtemp())
        self.weapons_file = self.temp_dir / "weapons_crafting.toml"
        self.armor_file = self.temp_dir / "armor_crafting.toml"
        self.materials_file = self.temp_dir / "crafting_materials.toml"

        # Datos de prueba para armas
        test_weapons_data = """# Recetas de crafting - weapons
[weapons_recipes]
[[weapons_recipes.recipes]]
id = "Arma1"
name = "Daga"
index = 15
skill_requirement = 10
success_rate = 70
experience = 15
tier = 1
materials = [
    {item = "hierro", quantity = 2}
]

[[weapons_recipes.recipes]]
id = "Arma2"
name = "Espada Larga"
index = 2
skill_requirement = 20
success_rate = 60
experience = 25
tier = 2
materials = [
    {item = "hierro", quantity = 3},
    {item = "madera", quantity = 1}
]

[[weapons_recipes.recipes]]
id = "Arma3"
name = "Espada de Plata"
index = 403
skill_requirement = 30
success_rate = 50
experience = 35
tier = 3
materials = [
    {item = "plata", quantity = 2}
]
"""

        # Datos de prueba para armaduras
        test_armor_data = """# Recetas de crafting - armor
[armor_recipes]
[[armor_recipes.recipes]]
id = "Armadura1"
name = "Casco de Hierro"
index = 132
skill_requirement = 15
success_rate = 65
experience = 20
tier = 1
materials = [
    {item = "hierro", quantity = 2}
]

[[armor_recipes.recipes]]
id = "Armadura2"
name = "Armadura de Plata"
index = 405
skill_requirement = 35
success_rate = 45
experience = 40
tier = 3
materials = [
    {item = "plata", quantity = 3}
]
"""

        # Datos de prueba para materiales
        test_materials_data = """# Materiales base para crafting
[crafting_materials]
[[crafting_materials.materials]]
id = "hierro"
name = "Lingote de Hierro"
index = 1
skill_requirement = 5

[[crafting_materials.materials]]
id = "plata"
name = "Lingote de Plata"
index = 2
skill_requirement = 15

[[crafting_materials.materials]]
id = "madera"
name = "Leña"
index = 5
skill_requirement = 1
"""

        self.weapons_file.write_text(test_weapons_data, encoding="utf-8")
        self.armor_file.write_text(test_armor_data, encoding="utf-8")
        self.materials_file.write_text(test_materials_data, encoding="utf-8")

        self.service = CraftingService(self.temp_dir)

    def teardown_method(self):
        """Limpieza después de cada test."""
        # Eliminar archivos temporales
        shutil.rmtree(self.temp_dir)

    def test_load_crafting_data(self):
        """Test que los datos de crafting se cargan correctamente."""
        assert len(self.service.get_weapon_recipes()) == 3
        assert len(self.service.get_armor_recipes()) == 2
        assert len(self.service.get_all_materials()) == 3
        assert len(self.service.get_all_recipes()) == 5

    def test_get_recipes_by_skill(self):
        """Test filtrado de recetas por nivel de skill."""
        # Skill bajo
        skill_5_recipes = self.service.get_recipes_by_skill(5)
        assert len(skill_5_recipes) == 0

        # Skill medio
        skill_12_recipes = self.service.get_recipes_by_skill(12)
        assert len(skill_12_recipes) == 1  # Solo Daga (skill 10)

        # Skill 15
        skill_15_recipes = self.service.get_recipes_by_skill(15)
        assert len(skill_15_recipes) == 2  # Daga y Casco Hierro

        # Skill alto
        skill_40_recipes = self.service.get_recipes_by_skill(40)
        assert len(skill_40_recipes) == 5  # Todas las recetas

    def test_get_recipe_by_index(self):
        """Test búsqueda de recetas por index."""
        daga_recipe = self.service.get_recipe_by_index(15)
        assert daga_recipe is not None
        assert daga_recipe["name"] == "Daga"
        assert daga_recipe["skill_requirement"] == 10

        # Receta inexistente
        invalid_recipe = self.service.get_recipe_by_index(9999)
        assert invalid_recipe is None

    def test_can_craft_success(self):
        """Test verificación de crafting exitoso."""
        daga_recipe = self.service.get_recipe_by_index(15)
        inventory = {"hierro": 5}

        can_craft, reason = self.service.can_craft(daga_recipe, inventory, 15)
        assert can_craft is True
        assert "Puedes crear" in reason

    def test_can_craft_insufficient_skill(self):
        """Test verificación de crafting con skill insuficiente."""
        espada_recipe = self.service.get_recipe_by_index(2)
        inventory = {"hierro": 5, "madera": 2}

        can_craft, reason = self.service.can_craft(espada_recipe, inventory, 15)
        assert can_craft is False
        assert "Skill insuficiente" in reason
        assert "20" in reason
        assert "15" in reason

    def test_can_craft_insufficient_materials(self):
        """Test verificación de crafting con materiales insuficientes."""
        daga_recipe = self.service.get_recipe_by_index(15)
        inventory = {"hierro": 1}  # Necesita 2

        can_craft, reason = self.service.can_craft(daga_recipe, inventory, 15)
        assert can_craft is False
        assert "Material insuficiente" in reason

    def test_craft_item_success(self):
        """Test creación de item exitoso."""
        daga_recipe = self.service.get_recipe_by_index(15)
        inventory = {"hierro": 5}

        # Forzar éxito mockeando random
        # ruff: noqa: S311 - standard random is fine for tests
        original_random = random.randint
        random.randint = lambda _a, _b: 50  # Siempre exito

        try:
            success, item, msg = self.service.craft_item(daga_recipe, inventory, 15)
            assert success is True
            assert item is not None
            assert item["name"] == "Daga"
            assert item["index"] == 15
            assert "creado con éxito" in msg
            # Verificar que consumió materiales
            assert inventory["hierro"] == 3
        finally:
            random.randint = original_random

    def test_craft_item_failure(self):
        """Test fallo en crafting."""
        daga_recipe = self.service.get_recipe_by_index(15)
        inventory = {"hierro": 3}

        # Forzar fallo mockeando random
        # ruff: noqa: S311 - standard random is fine for tests
        original_random = random.randint
        random.randint = lambda _a, _b: 100  # Siempre fallo

        try:
            success, item, msg = self.service.craft_item(daga_recipe, inventory, 15)
            assert success is False
            assert item is None
            assert "Falló el crafting" in msg
            # Verificar que consumió la mitad de materiales
            assert inventory["hierro"] == 2
        finally:
            random.randint = original_random

    def test_craft_item_skill_bonus(self):
        """Test bonus de skill en crafting."""
        espada_recipe = self.service.get_recipe_by_index(2)
        inventory = {"hierro": 10, "madera": 5}

        # Mock random para testing
        # ruff: noqa: S311 - standard random is fine for tests
        calls = []

        def mock_randint(_a, _b):
            calls.append((_a, _b))
            return 50  # Base rate 60 + bonus 10 = 70, pero 50 < 70

        original_random = random.randint
        random.randint = mock_randint

        try:
            success, _item, msg = self.service.craft_item(espada_recipe, inventory, 30)  # 10+ skill
            assert success is True
            assert "exp" in msg  # Verificar que ganó experiencia
        finally:
            random.randint = original_random

    def test_get_material_info(self):
        """Test obtener información de materiales."""
        hierro_info = self.service.get_material_info("hierro")
        assert hierro_info is not None
        assert hierro_info["name"] == "Lingote de Hierro"
        assert hierro_info["skill_requirement"] == 5

        # Material inexistente
        invalid_info = self.service.get_material_info("invalid")
        assert invalid_info is None

    def test_calculate_crafting_cost(self):
        """Test cálculo de costo de recetas."""
        espada_recipe = self.service.get_recipe_by_index(2)
        cost = self.service.calculate_crafting_cost(espada_recipe)

        assert cost["total_materials"] == 2
        assert len(cost["materials"]) == 2
        assert cost["difficulty"] == 20
        assert cost["success_rate"] == 60

        # Verificar detalles de materiales
        material_names = [m["name"] for m in cost["materials"]]
        assert "Lingote de Hierro" in material_names
        assert "Leña" in material_names

    def test_get_available_tiers(self):
        """Test obtener tiers disponibles."""
        # Skill bajo
        tiers_5 = self.service.get_available_tiers(5)
        assert len(tiers_5) == 0

        # Skill medio
        tiers_12 = self.service.get_available_tiers(12)
        assert tiers_12 == [1]

        # Skill alto
        tiers_40 = self.service.get_available_tiers(40)
        assert sorted(tiers_40) == [1, 2, 3]

    def test_crafting_with_no_materials(self):
        """Test crafting sin materiales en inventario."""
        daga_recipe = self.service.get_recipe_by_index(15)
        inventory = {}

        can_craft, reason = self.service.can_craft(daga_recipe, inventory, 15)
        assert can_craft is False
        assert "No tienes" in reason

    def test_crafting_complex_recipe(self):
        """Test receta compleja con múltiples materiales."""
        espada_recipe = self.service.get_recipe_by_index(2)
        inventory = {"hierro": 5, "madera": 3}

        # Test puede crear
        can_craft, _reason = self.service.can_craft(espada_recipe, inventory, 25)
        assert can_craft is True

        # Test crafting (forzar exito)
        # ruff: noqa: S311 - standard random is fine for tests
        original_random = random.randint
        random.randint = lambda _a, _b: 50

        try:
            success, _item, _msg = self.service.craft_item(espada_recipe, inventory, 25)
            assert success is True
            # Verificar que consumió materiales correctos
            assert inventory["hierro"] == 2
            assert inventory["madera"] == 2
        finally:
            random.randint = original_random

    def test_missing_crafting_files(self):
        """Test comportamiento cuando no existen archivos de crafting."""
        empty_dir = Path(tempfile.mkdtemp())
        try:
            service = CraftingService(empty_dir)
            # No debería cargar nada
            assert len(service.get_weapon_recipes()) == 0
            assert len(service.get_armor_recipes()) == 0
            assert len(service.get_all_materials()) == 0
        finally:
            shutil.rmtree(empty_dir)

    def test_integration_with_real_data(self):
        """Test de integración con datos reales del cliente."""
        # Usar datos reales si existen
        real_weapons_file = Path("data/weapons_crafting.toml")
        if real_weapons_file.exists():
            real_service = CraftingService(Path("data"))

            # Verificar que cargue datos reales
            assert len(real_service.get_weapon_recipes()) > 0
            assert len(real_service.get_all_materials()) > 0

            # Verificar datos específicos
            daga_recipe = real_service.get_recipe_by_index(15)
            assert daga_recipe is not None
            assert "Daga" in daga_recipe["name"]
            assert daga_recipe["skill_requirement"] > 0
