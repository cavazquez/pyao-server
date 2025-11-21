#!/usr/bin/env python3
"""
Extractor de datos de Crafting del cliente Argentum Online.

Extrae las listas de items craftables desde archivos .dat y genera
recetas balanceadas con materiales y requerimientos de skill.
"""

import re
from pathlib import Path
from typing import Dict, List, Any, Tuple
import random


class CraftingDataExtractor:
    def __init__(self, data_dir: Path, output_dir: Path):
        self.data_dir = data_dir
        self.output_dir = output_dir
        self.output_dir.mkdir(exist_ok=True)

        # Materiales base para crafting
        self.base_materials = {
            "hierro": {"index": 1, "name": "Lingote de Hierro", "skill_req": 10},
            "plata": {"index": 2, "name": "Lingote de Plata", "skill_req": 30},
            "oro": {"index": 3, "name": "Lingote de Oro", "skill_req": 50},
            "acero": {"index": 4, "name": "Lingote de Acero", "skill_req": 40},
            "madera": {"index": 5, "name": "Leña", "skill_req": 1},
            "cuero": {"index": 6, "name": "Piel de Animal", "skill_req": 5},
            "hueso": {"index": 7, "name": "Hueso de Animal", "skill_req": 3},
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
        name = item["name"].lower()
        
        # Determinar materiales base según el nombre
        materials = []
        skill_req = 5 + (tier * 10)
        
        if "daga" in name or "espada" in name or "hacha" in name:
            # Armas de metal
            if "plata" in name:
                materials.append({"item": "plata", "quantity": 2 + tier})
                skill_req += 20
            elif "dragon" in name or "mata dragones" in name:
                materials.append({"item": "acero", "quantity": 3 + tier})
                skill_req += 30
            elif "barbaro" in name or "guerra" in name:
                materials.append({"item": "hierro", "quantity": 3 + tier})
                skill_req += 15
            else:
                materials.append({"item": "hierro", "quantity": 1 + tier})
            
            if "mango" in name or "vara" in name:
                materials.append({"item": "madera", "quantity": 1})
                
        elif "casco" in name or "armadura" in name or "cota" in name:
            # Armaduras
            if "plata" in name:
                materials.append({"item": "plata", "quantity": 3 + tier})
                skill_req += 20
            elif "dragon" in name or "dorada" in name:
                materials.append({"item": "acero", "quantity": 4 + tier})
                skill_req += 30
            elif "hierro" in name:
                materials.append({"item": "hierro", "quantity": 2 + tier})
            else:
                materials.append({"item": "cuero", "quantity": 2 + tier})
                skill_req -= 5
                
        elif "escudo" in name:
            # Escudos
            if "plata" in name:
                materials.append({"item": "plata", "quantity": 3 + tier})
                skill_req += 25
            elif "tortuga" in name:
                materials.append({"item": "hueso", "quantity": 3})
                skill_req += 10
            else:
                materials.append({"item": "hierro", "quantity": 2 + tier})
                
        elif "hacha de leñador" in name or "serrucho" in name or "piquete" in name:
            # Herramientas
            materials.append({"item": "hierro", "quantity": 1})
            materials.append({"item": "madera", "quantity": 2})
            skill_req = max(5, skill_req - 10)
            
        elif "flecha" in name:
            # Munición
            materials.append({"item": "madera", "quantity": 5})
            materials.append({"item": "hueso", "quantity": 2})
            skill_req = max(1, skill_req - 15)
            
        elif "laud" in name:
            # Instrumentos
            materials.append({"item": "madera", "quantity": 3})
            if "mágico" in name or "élfico" in name:
                skill_req += 25
                
        else:
            # Default - materiales básicos
            materials.append({"item": "hierro", "quantity": 1})
            materials.append({"item": "madera", "quantity": 1})
        
        # Añadir chance de éxito basado en skill
        success_rate = min(95, 50 + (skill_req // 2))
        
        return {
            "item_id": item["id"],
            "item_name": item["name"],
            "item_index": item["index"],
            "skill_requirement": max(1, skill_req),
            "materials": materials,
            "success_rate": success_rate,
            "experience": 10 + (tier * 5),
            "tier": tier
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
        weapons = [r for r in recipes if "item_id" in r and "Arma" in r["item_id"]]
        armor = [r for r in recipes if "item_id" in r and "Armadura" in r["item_id"]]
        
        # Guardar armas
        weapons_file = self.output_dir / "weapons_crafting.toml"
        weapons_toml = self.convert_recipes_to_toml(weapons, "weapons")
        with open(weapons_file, 'w', encoding='utf-8') as f:
            f.write(weapons_toml)
        print(f"✅ Armas guardadas en: {weapons_file}")
        
        # Guardar armaduras
        armor_file = self.output_dir / "armor_crafting.toml"
        armor_toml = self.convert_recipes_to_toml(armor, "armor")
        with open(armor_file, 'w', encoding='utf-8') as f:
            f.write(armor_toml)
        print(f"✅ Armaduras guardadas en: {armor_file}")
        
        # Guardar materiales
        materials_file = self.output_dir / "crafting_materials.toml"
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
                toml_content.append(f'    {{item = "{material["item"]}", quantity = {material["quantity"]}}},')
            if recipe["materials"]:
                toml_content[-1] = toml_content[-1][:-1]  # Eliminar última coma
            toml_content.append("]")
            toml_content.append("")
        
        return '\n'.join(toml_content)

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
        
        return '\n'.join(toml_content)


def main():
    base_dir = Path(__file__).parent.parent
    data_dir = base_dir / "clientes" / "ArgentumOnline0.13.3-Cliente-Servidor" / "server" / "Dat"
    output_dir = base_dir / "data"
    
    if not data_dir.exists():
        print(f"Error: No existe {data_dir}")
        return
    
    extractor = CraftingDataExtractor(data_dir, output_dir)
    extractor.extract_all_crafting_data()
    
    print("\n✅ Extracción de datos de crafting completada!")


if __name__ == "__main__":
    main()
