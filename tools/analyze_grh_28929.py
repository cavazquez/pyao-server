#!/usr/bin/env python3
"""Analiza el GrhIndex 28929 para determinar si es un árbol o tile de terreno"""
import struct
from pathlib import Path
from collections import defaultdict

def read_full_map(map_path):
    """Lee todo el mapa y retorna diccionario de tiles"""
    header_size = 273
    map_width = 100
    map_height = 100
    tiles = {}
    
    with open(map_path, 'rb') as f:
        for y in range(1, 101):
            for x in range(1, 101):
                tile_index = (y - 1) * map_width + (x - 1)
                layers = {}
                
                for i, layer_name in enumerate(['ground', 'obj1', 'obj2']):
                    layer_offset = header_size + (i * map_width * map_height * 2)
                    tile_offset = layer_offset + (tile_index * 2)
                    f.seek(tile_offset)
                    data = f.read(2)
                    if len(data) == 2:
                        layers[layer_name] = struct.unpack('<H', data)[0]
                    else:
                        layers[layer_name] = 0
                
                tiles[(x, y)] = layers
    
    return tiles

# Analizar Mapa 1
map_path = '/home/cristian/repos/propios/pyao-server/clientes/ArgentumOnline0.13.3-Cliente-Servidor/server/Maps/Mapa1.map'
tiles = read_full_map(map_path)

target_grh = 28929
locations = []

print(f"\n🔍 Analizando GrhIndex {target_grh} en Mapa 1...\n")

for (x, y), layers in tiles.items():
    for layer_name, grh_value in layers.items():
        base_grh = grh_value & 0x7FFF
        if base_grh == target_grh:
            locations.append((x, y, layer_name, grh_value))

print(f"📊 Apariciones totales: {len(locations)}")
print(f"\nPrimeras 20 ubicaciones:")
print("-" * 60)

layer_stats = defaultdict(int)
for x, y, layer, grh_val in locations[:20]:
    layer_stats[layer] += 1
    print(f"  ({x:2d},{y:2d}) layer={layer:6s} grh={grh_val}")

print(f"\n📈 Distribución por layer:")
for layer, count in sorted(layer_stats.items()):
    print(f"  {layer:6s}: {count} apariciones")

print(f"\n💡 Análisis:")
if locations and locations[0][2] == 'ground':
    print("  ⚠️  Este GrhIndex está en la capa 'ground'")
    print("  ⚠️  Los árboles suelen estar en 'obj1' o 'obj2'")
    print("  ⚠️  Probablemente es un TILE DE TERRENO, no un árbol")
    print("  ⚠️  NO debería agregarse a trees.toml")
else:
    print("  ✅ Este GrhIndex está en capas de objetos")
    print("  ✅ Podría ser un árbol válido")
