"""Publica recetas propias validadas; la fabricación en juego sólo lee Redis."""

import json
import tomllib
from typing import Any

from src.models.item_catalog import ItemCatalog
from src.runtime_paths import data_dir
from src.utils.base_data_loader import BaseDataLoader

CRAFTING_KEY = "config:crafting:recipes"
MATERIALS = {"hierro": 386, "plata": 387, "oro": 388, "madera": 58}


def load_recipes() -> list[dict[str, Any]]:
    """Normaliza los tres catálogos sin confundir índices internos con objetos.

    Returns:
        Recetas de herrería, carpintería y fundición con materiales reales.

    Raises:
        ValueError: Si una receta referencia objetos o cantidades inexistentes.
    """
    catalog = ItemCatalog()
    recipes: list[dict[str, Any]] = []
    for filename, section, entries, skill in (
        ("weapons", "weapons_recipes", "recipes", "herreria"),
        ("armor", "armor_recipes", "recipes", "herreria"),
        ("carpentry", "carpentry", "recipe", "carpinteria"),
    ):
        data = tomllib.loads((data_dir() / "crafting" / f"{filename}.toml").read_text())
        for source in data[section][entries]:
            materials = [
                {
                    "item_id": int(
                        material.get("item_id", MATERIALS.get(material.get("item", ""), 0))
                    ),
                    "quantity": int(material["quantity"]),
                }
                for material in source["materials"]
            ]
            item_id = int(source.get("index", source.get("item_id", 0)))
            if (
                not catalog.item_exists(item_id)
                or not materials
                or any(
                    not catalog.item_exists(m["item_id"]) or m["quantity"] < 1 for m in materials
                )
            ):
                message = f"Receta inválida: {filename}/{item_id}"
                raise ValueError(message)
            recipes.append(
                {
                    "id": f"{skill}:{item_id}",
                    "item_id": item_id,
                    "name": catalog.get_item_name(item_id),
                    "skill": skill,
                    "required": int(source.get("skill_requirement", source.get("skill_level", 0))),
                    "success_rate": int(source.get("success_rate", 80)),
                    "materials": materials,
                }
            )
    for ore in (192, 193, 194):
        item = catalog.get_item_data(ore) or {}
        recipes.append(
            {
                "id": f"fundir:{ore}",
                "item_id": int(str(item["Lingoteindex"])),
                "name": catalog.get_item_name(int(str(item["Lingoteindex"]))),
                "skill": "mineria",
                "required": int(str(item["MinSkill"])),
                "success_rate": 100,
                "materials": [{"item_id": ore, "quantity": 1}],
            }
        )
    identities = [recipe["id"] for recipe in recipes]
    if len(identities) != len(set(identities)):
        message = "El catálogo de fabricación contiene recetas duplicadas"
        raise ValueError(message)
    return recipes


class CraftingDataLoader(BaseDataLoader):
    """Catálogo cargado antes de aceptar jugadores."""

    def get_name(self) -> str:
        """Identifica el catálogo.

        Returns:
            Nombre de las recetas.
        """
        return "Crafting Recipes"

    async def load(self) -> None:
        """Carga recetas verificadas, sin modificar inventarios ni progreso."""
        await self.redis_client.redis.set(
            CRAFTING_KEY, json.dumps(load_recipes(), ensure_ascii=False), nx=True
        )
