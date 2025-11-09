#!/usr/bin/env python3
"""Verifica una coordenada específica en un mapa"""
import struct
import tomllib
from pathlib import Path

def load_trees_grh():
    """Carga todos los GrhIndex de árboles desde trees.toml"""
    trees_path = Path(__file__).parent.parent / "data/items/world_objects/trees.toml"
    with open(trees_path, 'rb') as f:
        data = tomllib.load(f)
    return {item['GrhIndex'] for item in data['item']}

def read_map_tile(map_path, x, y):
    """Lee un tile específico del mapa binario"""
    header_size = 273
    map_width = 100
    map_height = 100
    
    with open(map_path, 'rb') as f:
        tile_index = (y - 1) * map_width + (x - 1)
        layers = {}
        layer_names = ['ground', 'obj1', 'obj2']
        
        for i, layer_name in enumerate(layer_names):
            layer_offset = header_size + (i * map_width * map_height * 2)
            tile_offset = layer_offset + (tile_index * 2)
            f.seek(tile_offset)
            data = f.read(2)
            if len(data) == 2:
                layers[layer_name] = struct.unpack('<H', data)[0]
            else:
                layers[layer_name] = 0
        return layers

# Verificar coordenada
map_path = '/home/cristian/repos/propios/pyao-server/clientes/ArgentumOnline0.13.3-Cliente-Servidor/server/Maps/Mapa1.map'
x, y = 74, 92

print(f"\n=== Coordenada ({x},{y}) - Mapa 1 ===\n")

tiles = read_map_tile(map_path, x, y)
tree_grh_indices = load_trees_grh()

print(f"GrhIndex de árboles conocidos: {len(tree_grh_indices)}")
print(f"Algunos ejemplos: {sorted(list(tree_grh_indices))[:10]}\n")

for layer_name, grh_value in tiles.items():
    base_grh = grh_value & 0x7FFF
    has_flag = (grh_value & 0x8000) != 0
    print(f"{layer_name:8s}: {grh_value:5d} (0x{grh_value:04X}) -> base_grh={base_grh}, flag={has_flag}")
    
    if base_grh in tree_grh_indices:
        print(f"            ✅ ÁRBOL (GrhIndex={base_grh} está en trees.toml)")
    elif base_grh > 0:
        print(f"            ⚠️  GrhIndex={base_grh} NO está en trees.toml")
