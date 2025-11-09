#!/usr/bin/env python3
"""
Analiza los objetos extraídos de los mapas y encuentra los GrhIndex
de árboles que faltan en trees.toml
"""

import json
import tomllib
from pathlib import Path
from collections import Counter


def main():
    # Leer todos los objetos extraídos
    map_data_dir = Path(__file__).parent.parent / "map_data"
    tree_grh_indices = []
    mine_grh_indices = []
    
    print("📊 Analizando objetos extraídos de los mapas...\n")
    
    for json_file in sorted(map_data_dir.glob('objects_*.json')):
        with open(json_file, 'r') as f:
            for line in f:
                obj = json.loads(line.strip())
                if obj.get('t') == 'tree':
                    tree_grh_indices.append(obj['g'])
                elif obj.get('t') == 'mine':
                    mine_grh_indices.append(obj['g'])
    
    # Contar frecuencias
    tree_counter = Counter(tree_grh_indices)
    mine_counter = Counter(mine_grh_indices)
    
    print(f"🌳 Total de árboles encontrados: {len(tree_grh_indices)}")
    print(f"⛏️  Total de minas encontradas: {len(mine_grh_indices)}")
    print(f"🎨 GrhIndex únicos de árboles: {len(tree_counter)}")
    print(f"🎨 GrhIndex únicos de minas: {len(mine_counter)}\n")
    
    # Leer trees.toml para ver qué GrhIndex ya existen
    trees_toml = Path(__file__).parent.parent / "data/items/world_objects/trees.toml"
    with open(trees_toml, 'rb') as f:
        trees_data = tomllib.load(f)
        existing_tree_grh = {item['GrhIndex'] for item in trees_data['item']}
    
    # Leer mines.toml si existe
    mines_toml = Path(__file__).parent.parent / "data/items/world_objects/mines.toml"
    existing_mine_grh = set()
    if mines_toml.exists():
        with open(mines_toml, 'rb') as f:
            mines_data = tomllib.load(f)
            existing_mine_grh = {item['GrhIndex'] for item in mines_data['item']}
    
    # Encontrar los que faltan
    unique_tree_grh = set(tree_grh_indices)
    unique_mine_grh = set(mine_grh_indices)
    
    missing_tree_grh = sorted(unique_tree_grh - existing_tree_grh)
    missing_mine_grh = sorted(unique_mine_grh - existing_mine_grh)
    
    # Mostrar resultados para árboles
    print("=" * 70)
    print("🌳 ÁRBOLES")
    print("=" * 70)
    print(f"\nGrhIndex existentes en trees.toml: {len(existing_tree_grh)}")
    print(f"GrhIndex encontrados en mapas: {len(unique_tree_grh)}")
    print(f"GrhIndex FALTANTES: {len(missing_tree_grh)}\n")
    
    if missing_tree_grh:
        print("⚠️  GrhIndex de árboles que FALTAN en trees.toml:")
        print("-" * 70)
        for grh in missing_tree_grh:
            count = tree_counter[grh]
            print(f"  GrhIndex {grh:5d} - Aparece {count:4d} veces en los mapas")
        
        print("\n📝 Entradas TOML sugeridas para agregar a trees.toml:")
        print("-" * 70)
        
        # Obtener el último ID usado
        max_id = max(item['id'] for item in trees_data['item'])
        next_id = max_id + 1
        
        for grh in missing_tree_grh:
            print(f"""
[[item]]
id = {next_id}
Name = "Árbol"
GrhIndex = {grh}
ObjType = 4
Agarrable = 1
""")
            next_id += 1
    else:
        print("✅ Todos los GrhIndex de árboles ya están en trees.toml")
    
    # Mostrar resultados para minas
    print("\n" + "=" * 70)
    print("⛏️  MINAS")
    print("=" * 70)
    print(f"\nGrhIndex existentes en mines.toml: {len(existing_mine_grh)}")
    print(f"GrhIndex encontrados en mapas: {len(unique_mine_grh)}")
    print(f"GrhIndex FALTANTES: {len(missing_mine_grh)}\n")
    
    if missing_mine_grh:
        print("⚠️  GrhIndex de minas que FALTAN en mines.toml:")
        print("-" * 70)
        for grh in missing_mine_grh:
            count = mine_counter[grh]
            print(f"  GrhIndex {grh:5d} - Aparece {count:4d} veces en los mapas")
        
        if mines_toml.exists():
            with open(mines_toml, 'rb') as f:
                mines_data = tomllib.load(f)
                max_id = max(item['id'] for item in mines_data['item'])
                next_id = max_id + 1
        else:
            next_id = 1000  # Empezar desde 1000 para minas
        
        print("\n📝 Entradas TOML sugeridas para agregar a mines.toml:")
        print("-" * 70)
        
        for grh in missing_mine_grh:
            print(f"""
[[item]]
id = {next_id}
Name = "Yacimiento"
GrhIndex = {grh}
ObjType = 4
Agarrable = 1
""")
            next_id += 1
    else:
        print("✅ Todos los GrhIndex de minas ya están en mines.toml")
    
    # Resumen final
    print("\n" + "=" * 70)
    print("📊 RESUMEN")
    print("=" * 70)
    print(f"Total de árboles en mapas: {len(tree_grh_indices)}")
    print(f"Total de minas en mapas: {len(mine_grh_indices)}")
    print(f"GrhIndex únicos de árboles: {len(unique_tree_grh)}")
    print(f"GrhIndex únicos de minas: {len(unique_mine_grh)}")
    print(f"Árboles faltantes en trees.toml: {len(missing_tree_grh)}")
    print(f"Minas faltantes en mines.toml: {len(missing_mine_grh)}")
    print("=" * 70)


if __name__ == "__main__":
    main()
