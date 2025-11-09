#!/usr/bin/env python3
"""Verifica cuántos carteles hay en signs.toml y si están en los mapas"""
import tomllib
import json
from pathlib import Path

print("\n🔍 Verificando Carteles...\n")

# Cargar carteles desde TOML
signs_path = Path(__file__).parent.parent / "data/items/world_objects/signs.toml"
with open(signs_path, 'rb') as f:
    data = tomllib.load(f)
    signs_grh = {item['GrhIndex']: item['Name'] for item in data['item']}

print(f"📚 Cargados {len(signs_grh)} carteles desde signs.toml")
print(f"   GrhIndex range: {min(signs_grh.keys())} - {max(signs_grh.keys())}")

# Buscar en mapas extraídos
map_data_dir = Path(__file__).parent.parent / 'map_data'
signs_found = []

for objects_file in sorted(map_data_dir.glob('objects_*.json')):
    with open(objects_file, 'r', encoding='utf-8') as f:
        for line in f:
            obj = json.loads(line.strip())
            grh = obj.get('g')
            
            if grh in signs_grh:
                signs_found.append((obj['m'], obj['x'], obj['y'], grh, signs_grh[grh]))

print("\n" + "=" * 70)
if signs_found:
    print(f"✅ Carteles encontrados en mapas: {len(signs_found)}")
    for map_id, x, y, grh, name in signs_found[:10]:
        print(f"   Mapa {map_id:3d} ({x:2d},{y:2d}) GrhIndex={grh:4d} - {name}")
    if len(signs_found) > 10:
        print(f"   ... y {len(signs_found) - 10} más")
else:
    print("⚠️  NO se encontraron carteles en los mapas extraídos")
    print("   Los carteles NO están siendo extraídos")

print("=" * 70)
