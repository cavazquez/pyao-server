#!/usr/bin/env python3
"""Verifica si yunques y transiciones están cargados correctamente"""
import json
from pathlib import Path

print("\n🔍 Verificando Yunques y Transiciones...\n")

map_data_dir = Path(__file__).parent.parent / 'map_data'

# Verificar transiciones
print("=" * 70)
print("🚪 TRANSICIONES")
print("=" * 70)

transition_files = list(map_data_dir.glob('transitions_*.json'))
if transition_files:
    total_transitions = 0
    for trans_file in sorted(transition_files):
        count = sum(1 for _ in open(trans_file))
        total_transitions += count
        print(f"  {trans_file.name}: {count} transiciones")
    print(f"\n  ✅ Total: {total_transitions} transiciones")
else:
    print("  ❌ No se encontraron archivos de transiciones")

# Verificar yunques en mapas
print("\n" + "=" * 70)
print("🔨 YUNQUES Y FRAGUAS")
print("=" * 70)

# GrhIndex de yunques y fraguas
YUNQUE_GRH = 600
FRAGUA_GRH = 722

yunques_found = []
fraguas_found = []

# Buscar en archivos objects_*.json
for objects_file in sorted(map_data_dir.glob('objects_*.json')):
    with open(objects_file, 'r', encoding='utf-8') as f:
        for line in f:
            obj = json.loads(line.strip())
            grh = obj.get('g')
            
            if grh == YUNQUE_GRH:
                yunques_found.append((obj['m'], obj['x'], obj['y']))
            elif grh == FRAGUA_GRH:
                fraguas_found.append((obj['m'], obj['x'], obj['y']))

if yunques_found:
    print(f"\n  ✅ Yunques encontrados: {len(yunques_found)}")
    for map_id, x, y in yunques_found[:5]:
        print(f"     Mapa {map_id}: ({x},{y})")
    if len(yunques_found) > 5:
        print(f"     ... y {len(yunques_found) - 5} más")
else:
    print("  ⚠️  NO se encontraron yunques en los mapas")
    print("     Los yunques NO están siendo extraídos")

if fraguas_found:
    print(f"\n  ✅ Fraguas encontradas: {len(fraguas_found)}")
    for map_id, x, y in fraguas_found[:5]:
        print(f"     Mapa {map_id}: ({x},{y})")
    if len(fraguas_found) > 5:
        print(f"     ... y {len(fraguas_found) - 5} más")
else:
    print("  ⚠️  NO se encontraron fraguas en los mapas")
    print("     Las fraguas NO están siendo extraídas")

print("\n" + "=" * 70)
print("💡 NOTA")
print("=" * 70)
print("Los yunques y fraguas NO son recursos como árboles/minas.")
print("Son objetos estáticos del mapa que se usan para crafteo.")
print("Si no están extraídos, necesitas agregarlos al sistema de extracción.")
print("=" * 70)
