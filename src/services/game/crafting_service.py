"""Servicio de Crafting del juego.

Carga y gestiona las recetas de crafting para herrería
y armaduras desde los archivos TOML extraídos del cliente.
"""

from __future__ import annotations

import logging
import random
from pathlib import Path
from tomllib import load as tomllib_load
from typing import Any, ClassVar

logger = logging.getLogger(__name__)


class CraftingService:
    """Servicio centralizado para manejar el sistema de crafting."""

    _instance: ClassVar[CraftingService | None] = None

    def __init__(self, data_dir: Path | None = None) -> None:
        """Inicializa el servicio de crafting.

        Args:
            data_dir: Directorio donde se encuentran los datos de crafting.
        """
        if getattr(self, "_initialized", False):
            return

        self.data_dir = data_dir or Path("data")
        self.weapons_recipes: list[dict[str, Any]] = []
        self.armor_recipes: list[dict[str, Any]] = []
        self.materials: dict[str, dict[str, Any]] = {}
        self.crafting_data: dict[str, Any] = {}
        self._load_crafting_data()

        self._initialized = True

    def _load_crafting_data(self) -> None:
        """Carga los datos de crafting desde archivos TOML."""
        try:
            # Cargar recetas de armas
            weapons_file = self.data_dir / "weapons_crafting.toml"
            if weapons_file.exists():
                with weapons_file.open("rb") as f:
                    weapons_data = tomllib_load(f)
                    self.weapons_recipes = weapons_data.get("weapons_recipes", {}).get(
                        "recipes", []
                    )

            # Cargar recetas de armaduras
            armor_file = self.data_dir / "armor_crafting.toml"
            if armor_file.exists():
                with armor_file.open("rb") as f:
                    armor_data = tomllib_load(f)
                    self.armor_recipes = armor_data.get("armor_recipes", {}).get("recipes", [])

            # Cargar materiales
            materials_file = self.data_dir / "crafting_materials.toml"
            if materials_file.exists():
                with materials_file.open("rb") as f:
                    materials_data = tomllib_load(f)
                    materials_list = materials_data.get("crafting_materials", {}).get(
                        "materials", []
                    )
                    for material in materials_list:
                        self.materials[material["id"]] = material

            self.crafting_data = {
                "weapons": self.weapons_recipes,
                "armor": self.armor_recipes,
                "materials": self.materials,
            }

            logger.info(
                "Crafting cargado: %d armas, %d armaduras, %d materiales",
                len(self.weapons_recipes),
                len(self.armor_recipes),
                len(self.materials),
            )

        except Exception:
            logger.exception("Error cargando datos de crafting")

    def get_all_recipes(self) -> list[dict[str, Any]]:
        """Retorna todas las recetas disponibles.

        Returns:
            Lista completa de recetas de armas y armaduras.
        """
        return self.weapons_recipes + self.armor_recipes

    def get_weapon_recipes(self) -> list[dict[str, Any]]:
        """Retorna todas las recetas de armas.

        Returns:
            Lista de recetas de armas.
        """
        return self.weapons_recipes.copy()

    def get_armor_recipes(self) -> list[dict[str, Any]]:
        """Retorna todas las recetas de armaduras.

        Returns:
            Lista de recetas de armaduras.
        """
        return self.armor_recipes.copy()

    def get_recipes_by_skill(self, skill_level: int) -> list[dict[str, Any]]:
        """Retorna recetas disponibles para un nivel de skill específico.

        Args:
            skill_level: Nivel de skill del personaje.

        Returns:
            Lista de recetas que el personaje puede intentar.
        """
        return [
            recipe
            for recipe in self.get_all_recipes()
            if recipe.get("skill_requirement", 0) <= skill_level
        ]

    def get_recipe_by_index(self, item_index: int) -> dict[str, Any] | None:
        """Busca una receta por el index del item resultante.

        Args:
            item_index: Index del item a crear.

        Returns:
            Receta encontrada o None si no existe.
        """
        all_recipes = self.get_all_recipes()
        for recipe in all_recipes:
            if recipe.get("index") == item_index:
                return recipe
        return None

    @staticmethod
    def can_craft(
        recipe: dict[str, Any], player_inventory: dict[str, int], player_skill: int
    ) -> tuple[bool, str]:
        """Verifica si un jugador puede crear un item.

        Args:
            recipe: Receta a verificar.
            player_inventory: Inventario del jugador (item_id -> cantidad).
            player_skill: Nivel de skill del jugador.

        Returns:
            Tupla (puede_crear, motivo_error).
        """
        # Verificar nivel de skill
        required_skill = recipe.get("skill_requirement", 0)
        if player_skill < required_skill:
            return False, f"Skill insuficiente. Requiere {required_skill}, tienes {player_skill}"

        # Verificar materiales
        materials = recipe.get("materials", [])
        for material in materials:
            material_id = material.get("item")
            required_qty = material.get("quantity", 0)

            if material_id not in player_inventory:
                return False, f"No tienes {material.get('item', material_id)}"

            if player_inventory[material_id] < required_qty:
                return (
                    False,
                    (
                        f"Material insuficiente: {material.get('item', material_id)} "
                        f"(necesitas {required_qty}, tienes {player_inventory[material_id]})"
                    ),
                )

        return True, "Puedes crear este item"

    def craft_item(
        self, recipe: dict[str, Any], player_inventory: dict[str, int], player_skill: int
    ) -> tuple[bool, dict[str, Any] | None, str]:
        """Intenta crear un item.

        Args:
            recipe: Receta a crear.
            player_inventory: Inventario del jugador.
            player_skill: Nivel de skill del jugador.

        Returns:
            Tupla (exitoso, item_creado, mensaje).
        """
        can_craft, reason = self.can_craft(recipe, player_inventory, player_skill)
        if not can_craft:
            return False, None, reason

        success, context = self._roll_crafting_success(recipe, player_skill)
        if success:
            created_item, message = self._apply_success_outcome(recipe, player_inventory, context)
            return True, created_item, message

        message = self._apply_failure_outcome(recipe, player_inventory)
        return False, None, message

    @staticmethod
    def _roll_crafting_success(
        recipe: dict[str, Any], player_skill: int
    ) -> tuple[bool, dict[str, int]]:
        """Determina si el crafting es exitoso.

        Returns:
            Tupla con ``(éxito, contexto)``, donde *contexto* incluye datos auxiliares
            como el ``skill_bonus`` calculado.
        """
        success_rate = recipe.get("success_rate", 50)
        required_skill = recipe.get("skill_requirement", 0)
        skill_bonus = max(0, (player_skill - required_skill) // 10)
        final_success_rate = min(95, success_rate + (skill_bonus * 5))
        roll = random.randint(1, 100)
        return roll <= final_success_rate, {
            "skill_bonus": skill_bonus,
            "final_success_rate": final_success_rate,
        }

    @staticmethod
    def _apply_success_outcome(
        recipe: dict[str, Any],
        player_inventory: dict[str, int],
        context: dict[str, int],
    ) -> tuple[dict[str, Any], str]:
        """Aplica los efectos de un crafting exitoso.

        Returns:
            Tupla ``(item_creado, mensaje)`` con el resultado del crafting exitoso.
        """
        for material in recipe.get("materials", []):
            material_id = material.get("item")
            quantity = material.get("quantity", 0)
            if material_id in player_inventory:
                player_inventory[material_id] -= quantity
                if player_inventory[material_id] <= 0:
                    del player_inventory[material_id]

        created_item = {
            "index": recipe.get("index"),
            "name": recipe.get("name"),
            "id": recipe.get("id"),
        }

        exp_gained = recipe.get("experience", 10)
        skill_bonus_exp = min(exp_gained, context["skill_bonus"] * 2)
        total_exp = exp_gained + skill_bonus_exp
        message = f"✅ ¡{recipe.get('name')} creado con éxito! (+{total_exp} exp)"
        return created_item, message

    @staticmethod
    def _apply_failure_outcome(recipe: dict[str, Any], player_inventory: dict[str, int]) -> str:
        """Aplica los efectos de un crafting fallido.

        Returns:
            Mensaje descriptivo del fallo y materiales consumidos.
        """
        consumed_materials: list[str] = []
        for material in recipe.get("materials", []):
            material_id = material.get("item")
            required_qty = material.get("quantity", 0)
            consumed_qty = max(1, required_qty // 2)

            if material_id in player_inventory:
                player_inventory[material_id] -= consumed_qty
                if player_inventory[material_id] <= 0:
                    del player_inventory[material_id]
                consumed_materials.append(f"{consumed_qty}x {material_id}")

        consumed_text = ", ".join(consumed_materials) or "ningún material"
        return f"❌ Falló el crafting. Perdiste: {consumed_text}"

    def get_material_info(self, material_id: str) -> dict[str, Any] | None:
        """Obtiene información de un material.

        Args:
            material_id: ID del material.

        Returns:
            Información del material o None si no existe.
        """
        return self.materials.get(material_id)

    def get_all_materials(self) -> dict[str, dict[str, Any]]:
        """Retorna todos los materiales disponibles.

        Returns:
            Diccionario completo de materiales.
        """
        return self.materials.copy()

    def calculate_crafting_cost(self, recipe: dict[str, Any]) -> dict[str, Any]:
        """Calcula el costo en materiales de una receta.

        Args:
            recipe: Receta a analizar.

        Returns:
            Diccionario con costo total y detalles.
        """
        materials = recipe.get("materials", [])
        total_materials = len(materials)

        cost_details = []
        for material in materials:
            material_info = self.get_material_info(material.get("item"))
            if material_info:
                cost_details.append(
                    {
                        "name": material_info.get("name", material.get("item")),
                        "quantity": material.get("quantity"),
                        "id": material.get("item"),
                    }
                )

        return {
            "total_materials": total_materials,
            "materials": cost_details,
            "difficulty": recipe.get("skill_requirement", 0),
            "success_rate": recipe.get("success_rate", 50),
        }

    def get_available_tiers(self, skill_level: int) -> list[int]:
        """Retorna los tiers disponibles para un nivel de skill.

        Args:
            skill_level: Nivel de skill del jugador.

        Returns:
            Lista de tiers disponibles.
        """
        available_tiers: set[int] = set()
        for recipe in self.get_all_recipes():
            if recipe.get("skill_requirement", 0) <= skill_level:
                available_tiers.add(recipe.get("tier", 0))
        return sorted(available_tiers)

    @classmethod
    def get_instance(cls, data_dir: Path | None = None) -> CraftingService:
        """Obtiene la instancia singleton del servicio.

        Returns:
            Instancia única de ``CraftingService``.
        """
        if cls._instance is None:
            cls._instance = cls(data_dir=data_dir)
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reinicia la instancia singleton."""
        cls._instance = None


def get_crafting_service() -> CraftingService:
    """Retorna la instancia singleton del servicio de crafting.

    Returns:
        Instancia singleton de ``CraftingService``.
    """
    return CraftingService.get_instance()


def initialize_crafting_service(data_dir: Path | None = None) -> CraftingService:
    """Inicializa el servicio singleton con directorio personalizado.

    Args:
        data_dir: Directorio donde se encuentran los datos.

    Returns:
        Instancia del ``CraftingService``.
    """
    CraftingService.reset_instance()
    return CraftingService.get_instance(data_dir=data_dir)
