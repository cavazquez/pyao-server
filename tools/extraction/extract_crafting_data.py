#!/usr/bin/env python3
"""
Extractor de datos de Crafting del cliente Argentum Online.

Extrae las listas de items craftables desde archivos .dat y genera
recetas balanceadas con materiales y requerimientos de skill.
"""

import re
from pathlib import Path
from typing import Dict, List, Any, Tuple
import tomllib

from src.models.item_catalog import ItemCatalog


class CraftingDataExtractor:
    def __init__(self, data_dir: Path, output_dir: Path):
        self.data_dir = data_dir
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.catalog = ItemCatalog()
        self.existing = {}
        for path in self.output_dir.glob("*.toml"):
            data = tomllib.loads(path.read_text())
            for category in ("weapons_recipes", "armor_recipes"):
                for recipe in data.get(category, {}).get("recipes", []):
                    self.existing[recipe["index"]] = recipe

        # Materiales base para crafting
        self.base_materials = {
            "hierro": {"index": 386, "name": "Lingote de Hierro", "skill_req": 25},
            "plata": {"index": 387, "name": "Lingote de Plata", "skill_req": 50},
            "oro": {"index": 388, "name": "Lingote de Oro", "skill_req": 75},
            "madera": {"index": 58, "name": "Leña", "skill_req": 0},
        }

    def parse_crafting_file(self, file_path: Path) -> Dict[str, Any]:
        """Parsea un archivo de crafting .dat."""
        data = {"items": [], "total": 0}
        
        try:
            with open(file_path, 'r', encoding='latin1') as f:
                content = f.read()
            
            # Extraer número total
            total_match = re.search(r'Num.*?=(\d+)', content)
            if total_match:
                data["total"] = int(total_match.group(1))
            
            # Extraer items
            item_pattern = r'\[(.*?)\]\s*\'(.+?)\s*Index=(\d+)'
            for match in re.finditer(item_pattern, content):
                item_id = match.group(1)
                name = match.group(2).strip()
                index = int(match.group(3))
                
                data["items"].append({
                    "id": item_id,
                    "name": name,
                    "index": index
                })
                
        except Exception as e:
            print(f"Error leyendo {file_path}: {e}")
            
        return data

    def generate_recipe(self, item: Dict[str, Any], item_type: str, tier: int = 1) -> Dict[str, Any]:
        """Genera una receta balanceada para un item."""
        canonical = self.catalog.get_item_data(item["index"])
        if canonical is None:
            raise ValueError(f"Objeto inexistente en receta: {item['index']}")
        materials = [{"item_id": identifier, "quantity": int(canonical[field])}
                     for field, identifier in (("LingH", 386), ("LingP", 387), ("LingO", 388))
                     if int(canonical.get(field, 0)) > 0]
        if not materials:
            raise ValueError(f"Sin materiales canónicos: {item['index']}")
        skill_req = int(canonical.get("SkHerreria", 0))
        existing = self.existing.get(item["index"], {})
        return {
            "item_id": item["id"], "item_name": canonical["Name"], "item_index": item["index"],
            "skill_requirement": skill_req, "materials": materials,
            "success_rate": existing.get("success_rate", min(95, 50 + skill_req // 2)),
            "experience": existing.get("experience", 10 + tier * 5), "tier": tier,
        }

    def determine_tier(self, item: Dict[str, Any]) -> int:
        """Determina el tier del item según su nombre."""
        name = item["name"].lower()
        
        if any(keyword in name for keyword in ["+1", "+2", "+3", "+4"]):
            if "+4" in name:
                return 4
            elif "+3" in name:
                return 3
            elif "+2" in name:
                return 2
            else:
                return 1
        elif any(keyword in name for keyword in ["dragon", "dorada", "legendaria", "mata dragones"]):
            return 4
        elif any(keyword in name for keyword in ["barbaro", "plata", "guerra", "elite"]):
            return 3
        elif any(keyword in name for keyword in ["hierro", "larga", "dos manos", "completa"]):
            return 2
        else:
            return 1

    def extract_all_crafting_data(self) -> None:
        """Extrae y procesa todos los datos de crafting."""
        print("🔧 Extrayendo datos de crafting...")
        
        # Extraer armas
        weapons_file = self.data_dir / "ArmasHerrero.dat"
        weapons_data = self.parse_crafting_file(weapons_file)
        print(f"✅ Armas extraídas: {len(weapons_data['items'])}")
        
        # Extraer armaduras
        armor_file = self.data_dir / "ArmadurasHerrero.dat"
        armor_data = self.parse_crafting_file(armor_file)
        print(f"✅ Armaduras extraídas: {len(armor_data['items'])}")
        
        # Generar recetas
        all_recipes = []
        
        for item in weapons_data["items"]:
            tier = self.determine_tier(item)
            recipe = self.generate_recipe(item, "weapon", tier)
            all_recipes.append(recipe)
        
        for item in armor_data["items"]:
            tier = self.determine_tier(item)
            recipe = self.generate_recipe(item, "armor", tier)
            all_recipes.append(recipe)
        
        # Guardar datos
        self.save_crafting_data(all_recipes)
        
        print(f"📊 Estadísticas: {len(all_recipes)} recetas generadas")

    def save_crafting_data(self, recipes: List[Dict[str, Any]]) -> None:
        """Guarda los datos de crafting en formato TOML."""
        
        # Separar por tipo
        weapons = [r for r in recipes if "item_id" in r and re.fullmatch(r"Arma\d+", r["item_id"]) is not None]
        armor = [r for r in recipes if "item_id" in r and re.fullmatch(r"Armadura\d+", r["item_id"]) is not None]
        
        # Guardar armas
        weapons_file = self.output_dir / "weapons.toml"
        weapons_toml = self.convert_recipes_to_toml(weapons, "weapons")
        with open(weapons_file, 'w', encoding='utf-8') as f:
            f.write(weapons_toml)
        print(f"✅ Armas guardadas en: {weapons_file}")
        
        # Guardar armaduras
        armor_file = self.output_dir / "armor.toml"
        armor_toml = self.convert_recipes_to_toml(armor, "armor")
        with open(armor_file, 'w', encoding='utf-8') as f:
            f.write(armor_toml)
        print(f"✅ Armaduras guardadas en: {armor_file}")
        
        # Guardar materiales
        materials_file = self.output_dir / "materials.toml"
        materials_toml = self.convert_materials_to_toml()
        with open(materials_file, 'w', encoding='utf-8') as f:
            f.write(materials_toml)
        print(f"✅ Materiales guardados en: {materials_file}")

    def convert_recipes_to_toml(self, recipes: List[Dict[str, Any]], category: str) -> str:
        """Convierte recetas a formato TOML."""
        toml_content = []
        
        toml_content.append(f"# Recetas de crafting - {category}")
        toml_content.append(f"[{category}_recipes]")
        
        for recipe in recipes:
            toml_content.append(f"[[{category}_recipes.recipes]]")
            toml_content.append(f'id = "{recipe["item_id"]}"')
            toml_content.append(f'name = "{recipe["item_name"]}"')
            toml_content.append(f'index = {recipe["item_index"]}')
            toml_content.append(f'skill_requirement = {recipe["skill_requirement"]}')
            toml_content.append(f'success_rate = {recipe["success_rate"]}')
            toml_content.append(f'experience = {recipe["experience"]}')
            toml_content.append(f'tier = {recipe["tier"]}')
            
            # Materiales
            toml_content.append("materials = [")
            for material in recipe["materials"]:
                toml_content.append(f'    {{item_id = {material["item_id"]}, quantity = {material["quantity"]}}},')
            if recipe["materials"]:
                toml_content[-1] = toml_content[-1][:-1]  # Eliminar última coma
            toml_content.append("]")
            toml_content.append("")
        
        return '\n'.join(toml_content).rstrip() + '\n'

    def convert_materials_to_toml(self) -> str:
        """Convierte materiales a formato TOML."""
        toml_content = []
        
        toml_content.append("# Materiales base para crafting")
        toml_content.append("[crafting_materials]")
        
        for mat_id, mat_data in self.base_materials.items():
            toml_content.append(f'[[crafting_materials.materials]]')
            toml_content.append(f'id = "{mat_id}"')
            toml_content.append(f'name = "{mat_data["name"]}"')
            toml_content.append(f'index = {mat_data["index"]}')
            toml_content.append(f'skill_requirement = {mat_data["skill_req"]}')
            toml_content.append("")
        
        return '\n'.join(toml_content).rstrip() + '\n'


def main():
    base_dir = Path(__file__).resolve().parents[2]
    data_dir = base_dir / "clientes" / "ArgentumOnline0.13.3-Cliente-Servidor" / "server" / "Dat"
    output_dir = base_dir / "data" / "crafting"
    
    if not data_dir.exists():
        print(f"Error: No existe {data_dir}")
        return
    
    extractor = CraftingDataExtractor(data_dir, output_dir)
    extractor.extract_all_crafting_data()
    
    print("\n✅ Extracción de datos de crafting completada!")


if __name__ == "__main__":
    main()
