#!/usr/bin/env python3
"""Verifica un área de 5x5 alrededor de la coordenada"""
import struct
import tomllib
from pathlib import Path

def load_trees_grh():
    """Carga todos los GrhIndex de árboles desde trees.toml"""
    trees_path = Path(__file__).parent.parent / "data/items/world_objects/trees.toml"
    with open(trees_path, 'rb') as f:
        data = tomllib.load(f)
    return {item['GrhIndex']: item['Name'] for item in data['item']}

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
center_x, center_y = 74, 92
map_path = '/home/cristian/repos/propios/pyao-server/clientes/ArgentumOnline0.13.3-Cliente-Servidor/server/Maps/Mapa1.map'
tree_grh_map = load_trees_grh()

print(f"\n🔍 Analizando área 5x5 alrededor de ({center_x},{center_y})...\n")

# Buscar en área 5x5
trees_found = []
objects_found = []

for dy in range(-2, 3):
    for dx in range(-2, 3):
        x = center_x + dx
        y = center_y + dy
        
        if x < 1 or x > 100 or y < 1 or y > 100:
            continue
        
        tiles = read_map_tile(map_path, x, y)
        
        for layer_name, grh_value in tiles.items():
            base_grh = grh_value & 0x7FFF
            
            if base_grh == 0:
                continue
            
            # Árbol conocido
            if base_grh in tree_grh_map:
                trees_found.append((x, y, layer_name, base_grh, tree_grh_map[base_grh]))
            # Objeto en capa obj1/obj2 (podría ser árbol no registrado)
            elif layer_name in ['obj1', 'obj2']:
                objects_found.append((x, y, layer_name, base_grh))

print("=" * 70)
print("🌳 ÁRBOLES CONOCIDOS (en trees.toml)")
print("=" * 70)
if trees_found:
    for x, y, layer, grh, name in trees_found:
        offset_x = x - center_x
        offset_y = y - center_y
        print(f"  ({x},{y}) [offset: {offset_x:+d},{offset_y:+d}] layer={layer:6s} grh={grh:5d} - {name}")
else:
    print("  ❌ No se encontraron árboles conocidos")

print("\n" + "=" * 70)
print("❓ OBJETOS DESCONOCIDOS (en obj1/obj2, NO en trees.toml)")
print("=" * 70)
if objects_found:
    for x, y, layer, grh in objects_found:
        offset_x = x - center_x
        offset_y = y - center_y
        print(f"  ({x},{y}) [offset: {offset_x:+d},{offset_y:+d}] layer={layer:6s} grh={grh:5d} ⚠️  NO REGISTRADO")
else:
    print("  ✅ No hay objetos desconocidos")

print("\n💡 Sugerencia:")
if not trees_found and not objects_found:
    print("  No hay árboles ni objetos en el área 5x5")
    print("  El árbol que ves podría ser:")
    print("    1. Un gráfico de terreno (ground layer)")
    print("    2. Estar en una coordenada más alejada")
    print("    3. Ser renderizado solo por el cliente")
elif objects_found:
    print("  Hay objetos desconocidos que podrían ser árboles")
    print("  Verifica estos GrhIndex en el servidor VB6 original")
