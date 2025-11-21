#!/usr/bin/env python3
"""Busca un GrhIndex específico en todos los mapas extraídos"""
import json
import sys
from pathlib import Path
from collections import defaultdict

# GrhIndex a buscar
target_grh = int(sys.argv[1]) if len(sys.argv) > 1 else 1460

print(f"\n🔍 Buscando GrhIndex {target_grh} en todos los mapas...\n")

map_data_dir = Path(__file__).parent.parent / 'map_data'
locations = defaultdict(list)

# Buscar en todos los archivos objects_*.json
for objects_file in sorted(map_data_dir.glob('objects_*.json')):
    with open(objects_file, 'r', encoding='utf-8') as f:
        for line in f:
            obj = json.loads(line.strip())
            if obj.get('g') == target_grh:
                map_id = obj['m']
                x = obj['x']
                y = obj['y']
                obj_type = obj['t']
                locations[map_id].append((x, y, obj_type))

if not locations:
    print(f"❌ GrhIndex {target_grh} NO encontrado en ningún mapa")
else:
    print(f"✅ GrhIndex {target_grh} encontrado en {len(locations)} mapa(s):\n")
    print("=" * 70)
    
    total_count = 0
    for map_id in sorted(locations.keys()):
        coords = locations[map_id]
        total_count += len(coords)
        obj_type = coords[0][2]
        
        print(f"Mapa {map_id:3d}: {len(coords):3d} apariciones (tipo: {obj_type})")
        
        # Mostrar primeras 5 coordenadas
        if len(coords) <= 5:
            for x, y, _ in coords:
                print(f"         ({x},{y})")
        else:
            for x, y, _ in coords[:3]:
                print(f"         ({x},{y})")
            print(f"         ... y {len(coords) - 3} más")
    
    print("=" * 70)
    print(f"Total: {total_count} apariciones en {len(locations)} mapa(s)")
