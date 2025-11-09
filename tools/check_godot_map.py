#!/usr/bin/env python3
"""Verifica el GrhIndex de tiles específicos en el mapa de Godot."""
import struct
from pathlib import Path

def get_tile_info(map_path, target_x, target_y):
    """Obtiene información de un tile específico."""
    header_size = 273
    
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
                trigger = 0
                if flags & 0x10:
                    trigger_data = f.read(2)
                    if len(trigger_data) == 2:
                        trigger = struct.unpack('<H', trigger_data)[0]
                
                # Si es el tile que buscamos
                if x == target_x and y == target_y:
                    return {
                        "x": x,
                        "y": y,
                        "blocked": bool(flags & 0x1),
                        "ground": layer1 & 0x7FFF,
                        "obj1": (layer2 & 0x7FFF) if layer2 > 0 else None,
                        "obj2": (layer3 & 0x7FFF) if layer3 > 0 else None,
                        "trigger": trigger if trigger > 0 else None,
                    }
    
    return None

# Verificar tiles (48, 65) y (49, 65) en mapa de Godot
map_path = Path('/home/cristian/repos/propios/pyao-server/clientes/ArgentumOnlineGodot/Assets/Maps/mapa1.map')

print("Verificando tiles en mapa de Godot (mapa1.map)...\n")

for x, y in [(48, 65), (49, 65)]:
    info = get_tile_info(map_path, x, y)
    if info:
        print(f"Tile ({x}, {y}):")
        print(f"  Bloqueado: {info['blocked']}")
        print(f"  Ground (layer1): {info['ground']}")
        print(f"  Obj1 (layer2): {info['obj1']}")
        print(f"  Obj2 (layer3): {info['obj2']}")
        print(f"  Trigger: {info['trigger']}")
        print()
