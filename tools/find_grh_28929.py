#!/usr/bin/env python3
"""Busca todas las apariciones del GrhIndex 28929 en los mapas"""
import struct
from pathlib import Path

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

# Buscar en todos los mapas
maps_dir = Path('/home/cristian/repos/propios/pyao-server/clientes/ArgentumOnline0.13.3-Cliente-Servidor/server/Maps')
target_grh = 28929

print(f"\n🔍 Buscando GrhIndex {target_grh} en todos los mapas...\n")

found_count = 0
for map_file in sorted(maps_dir.glob('Mapa*.map')):
    map_num = int(map_file.stem.replace('Mapa', ''))
    
    for y in range(1, 101):
        for x in range(1, 101):
            tiles = read_map_tile(str(map_file), x, y)
            
            for layer_name, grh_value in tiles.items():
                base_grh = grh_value & 0x7FFF
                
                if base_grh == target_grh:
                    found_count += 1
                    if found_count <= 10:  # Mostrar solo primeros 10
                        print(f"Mapa {map_num:3d} ({x:2d},{y:2d}) layer={layer_name:6s} grh={grh_value}")

print(f"\n✓ Total de apariciones: {found_count}")
