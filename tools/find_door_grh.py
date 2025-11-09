#!/usr/bin/env python3
"""Busca GrhIndex de puertas en un mapa específico."""
import struct
from pathlib import Path

def find_grh_in_map(map_path, target_grh_list):
    """Busca GrhIndex específicos en un mapa."""
    header_size = 273
    found = []
    
    with open(map_path, 'rb') as f:
        f.seek(header_size)
        
        for y in range(1, 101):
            for x in range(1, 101):
                # Leer flags
                flags_data = f.read(1)
                if len(flags_data) != 1:
                    continue
                flags = flags_data[0]
                
                # Layer 1 (ground)
                layer1_data = f.read(2)
                if len(layer1_data) != 2:
                    continue
                layer1 = struct.unpack('<H', layer1_data)[0]
                
                # Layer 2 (obj1)
                layer2 = 0
                if flags & 0x2:
                    layer2_data = f.read(2)
                    if len(layer2_data) == 2:
                        layer2 = struct.unpack('<H', layer2_data)[0]
                
                # Layer 3 (obj2)
                layer3 = 0
                if flags & 0x4:
                    layer3_data = f.read(2)
                    if len(layer3_data) == 2:
                        layer3 = struct.unpack('<H', layer3_data)[0]
                
                # Layer 4
                if flags & 0x8:
                    f.read(2)
                
                # Trigger
                if flags & 0x10:
                    f.read(2)
                
                # Verificar todas las capas
                for layer_name, layer_grh in [("ground", layer1), ("obj1", layer2), ("obj2", layer3)]:
                    if layer_grh == 0:
                        continue
                    
                    base_grh = layer_grh & 0x7FFF
                    
                    if base_grh in target_grh_list:
                        found.append({
                            "x": x,
                            "y": y,
                            "grh": base_grh,
                            "layer": layer_name,
                            "blocked": bool(flags & 0x1)
                        })
    
    return found

# Buscar en mapa 1
map_path = Path('/home/cristian/repos/propios/pyao-server/clientes/ArgentumOnline0.13.3-Cliente-Servidor/server/Maps/Mapa1.map')

# GrhIndex de puertas
door_grh_list = [5592, 5593, 5599, 5600, 8684, 8685, 9193, 9194, 9195, 9196, 9197, 9198, 9199, 9200, 9201, 9202, 9203, 9204]

print(f"Buscando {len(door_grh_list)} GrhIndex de puertas en Mapa 1...")
results = find_grh_in_map(map_path, door_grh_list)

if results:
    print(f"\n✓ Encontradas {len(results)} puertas:")
    for r in results[:10]:  # Mostrar primeras 10
        print(f"  ({r['x']:3d}, {r['y']:3d}) - GrhIndex={r['grh']} - Layer={r['layer']} - Blocked={r['blocked']}")
    if len(results) > 10:
        print(f"  ... y {len(results) - 10} más")
else:
    print("\n✗ No se encontraron puertas con esos GrhIndex")
