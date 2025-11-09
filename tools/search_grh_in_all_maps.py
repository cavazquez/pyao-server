#!/usr/bin/env python3
"""Busca GrhIndex específicos en TODAS las capas de todos los mapas"""
import struct
import sys
from pathlib import Path

# GrhIndex a buscar
target_grh_list = [600, 722]  # Yunque y Fragua

if len(sys.argv) > 1:
    target_grh_list = [int(g) for g in sys.argv[1:]]

print(f"\n🔍 Buscando GrhIndex {target_grh_list} en todos los mapas VB6...\n")

maps_dir = Path('/home/cristian/repos/propios/pyao-server/clientes/ArgentumOnline0.13.3-Cliente-Servidor/server/Maps')

found_locations = {grh: [] for grh in target_grh_list}

for map_file in sorted(maps_dir.glob('Mapa*.map')):
    map_id = int(map_file.stem.replace('Mapa', ''))
    
    with open(map_file, 'rb') as f:
        header_size = 273
        f.seek(header_size)
        
        for y in range(1, 101):
            for x in range(1, 101):
                # Leer flags
                flags_data = f.read(1)
                if len(flags_data) != 1:
                    continue
                flags = flags_data[0]
                
                # Layer 1
                layer1_data = f.read(2)
                if len(layer1_data) == 2:
                    layer1 = struct.unpack('<H', layer1_data)[0]
                    base_grh = layer1 & 0x7FFF
                    if base_grh in target_grh_list:
                        found_locations[base_grh].append((map_id, x, y, 'layer1'))
                
                # Layer 2
                if flags & 0x2:
                    layer2_data = f.read(2)
                    if len(layer2_data) == 2:
                        layer2 = struct.unpack('<H', layer2_data)[0]
                        base_grh = layer2 & 0x7FFF
                        if base_grh in target_grh_list:
                            found_locations[base_grh].append((map_id, x, y, 'layer2'))
                
                # Layer 3
                if flags & 0x4:
                    layer3_data = f.read(2)
                    if len(layer3_data) == 2:
                        layer3 = struct.unpack('<H', layer3_data)[0]
                        base_grh = layer3 & 0x7FFF
                        if base_grh in target_grh_list:
                            found_locations[base_grh].append((map_id, x, y, 'layer3'))
                
                # Layer 4
                if flags & 0x8:
                    layer4_data = f.read(2)
                    if len(layer4_data) == 2:
                        layer4 = struct.unpack('<H', layer4_data)[0]
                        base_grh = layer4 & 0x7FFF
                        if base_grh in target_grh_list:
                            found_locations[base_grh].append((map_id, x, y, 'layer4'))
                
                # Trigger
                if flags & 0x10:
                    f.read(2)

print("=" * 70)
for grh in target_grh_list:
    locations = found_locations[grh]
    if locations:
        print(f"\n✅ GrhIndex {grh} encontrado: {len(locations)} veces")
        for map_id, x, y, layer in locations[:10]:
            print(f"   Mapa {map_id:3d} ({x:2d},{y:2d}) en {layer}")
        if len(locations) > 10:
            print(f"   ... y {len(locations) - 10} más")
    else:
        print(f"\n❌ GrhIndex {grh} NO encontrado en ningún mapa")

print("=" * 70)
