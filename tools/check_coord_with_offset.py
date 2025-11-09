#!/usr/bin/env python3
"""Verifica coordenadas con offset +/-1 en X e Y"""
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

# Coordenada reportada por el cliente
client_x, client_y = 74, 92
map_path = '/home/cristian/repos/propios/pyao-server/clientes/ArgentumOnline0.13.3-Cliente-Servidor/server/Maps/Mapa1.map'
tree_grh_indices = load_trees_grh()

print(f"\n🔍 Verificando coordenada del cliente ({client_x},{client_y}) y adyacentes...\n")

# Verificar coordenada exacta y con offsets
coords_to_check = [
    (client_x, client_y, "Cliente (exacto)"),
    (client_x + 1, client_y, "X+1"),
    (client_x - 1, client_y, "X-1"),
    (client_x, client_y + 1, "Y+1"),
    (client_x, client_y - 1, "Y-1"),
]

for x, y, label in coords_to_check:
    print(f"📍 {label}: ({x},{y})")
    print("-" * 70)
    
    tiles = read_map_tile(map_path, x, y)
    found_tree = False
    
    for layer_name, grh_value in tiles.items():
        base_grh = grh_value & 0x7FFF
        
        if base_grh > 0:
            in_trees = base_grh in tree_grh_indices
            status = "✅ ÁRBOL" if in_trees else "❌"
            
            if in_trees or layer_name != 'ground':
                print(f"  {layer_name:6s}: grh={base_grh:5d} {status}")
                if in_trees:
                    found_tree = True
    
    if not found_tree:
        print("  (sin árboles detectados)")
    
    print()
