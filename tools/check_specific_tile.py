#!/usr/bin/env python3
"""Verifica una coordenada específica en cualquier mapa"""
import struct
import sys
import tomllib
from pathlib import Path

def load_known_objects():
    """Carga todos los GrhIndex conocidos"""
    objects = {}
    
    # Árboles
    trees_path = Path(__file__).parent.parent / "data/items/world_objects/trees.toml"
    if trees_path.exists():
        with open(trees_path, 'rb') as f:
            data = tomllib.load(f)
            for item in data['item']:
                objects[item['GrhIndex']] = f"Árbol ({item['Name']})"
    
    # Minas
    mines_path = Path(__file__).parent.parent / "data/items/world_objects/mines.toml"
    if mines_path.exists():
        with open(mines_path, 'rb') as f:
            data = tomllib.load(f)
            for item in data['item']:
                objects[item['GrhIndex']] = f"Mina ({item['Name']})"
    
    return objects

def read_vb6_tile(map_path, x, y):
    """Lee un tile del mapa VB6"""
    header_size = 273
    
    with open(map_path, 'rb') as f:
        f.seek(header_size)
        
        for tile_y in range(1, 101):
            for tile_x in range(1, 101):
                flags_data = f.read(1)
                if len(flags_data) != 1:
                    return None
                flags = flags_data[0]
                
                layer1_data = f.read(2)
                if len(layer1_data) != 2:
                    return None
                layer1 = struct.unpack('<H', layer1_data)[0]
                
                layer2 = 0
                if flags & 0x2:
                    layer2_data = f.read(2)
                    if len(layer2_data) == 2:
                        layer2 = struct.unpack('<H', layer2_data)[0]
                
                layer3 = 0
                if flags & 0x4:
                    layer3_data = f.read(2)
                    if len(layer3_data) == 2:
                        layer3 = struct.unpack('<H', layer3_data)[0]
                
                if flags & 0x8:
                    f.read(2)
                
                if flags & 0x10:
                    f.read(2)
                
                if tile_x == x and tile_y == y:
                    return {
                        'flags': flags,
                        'blocked': bool(flags & 0x1),
                        'layer1': layer1,
                        'layer2': layer2,
                        'layer3': layer3,
                    }
    
    return None

# Parámetros
if len(sys.argv) >= 4:
    map_id = int(sys.argv[1])
    x = int(sys.argv[2])
    y = int(sys.argv[3])
else:
    map_id = 200
    x = 41
    y = 23

map_path = f'/home/cristian/repos/propios/pyao-server/clientes/ArgentumOnline0.13.3-Cliente-Servidor/server/Maps/Mapa{map_id}.map'

print(f"\n🔍 Analizando Mapa {map_id}, coordenada ({x},{y})\n")
print("=" * 70)

tile = read_vb6_tile(map_path, x, y)
known_objects = load_known_objects()

if tile:
    print(f"Flags: 0x{tile['flags']:02X}")
    print(f"Bloqueado: {'Sí' if tile['blocked'] else 'No'}")
    print()
    print(f"Layer1 (ground): {tile['layer1']}")
    print(f"Layer2 (obj1):   {tile['layer2']}")
    print(f"Layer3 (obj2):   {tile['layer3']}")
    print()
    
    # Identificar objetos
    print("=" * 70)
    print("OBJETOS IDENTIFICADOS")
    print("=" * 70)
    
    found_any = False
    
    for layer_name, grh_value in [('Layer2', tile['layer2']), ('Layer3', tile['layer3'])]:
        if grh_value == 0:
            continue
        
        base_grh = grh_value & 0x7FFF
        
        if base_grh in known_objects:
            print(f"✅ {layer_name}: {known_objects[base_grh]} (GrhIndex={base_grh})")
            found_any = True
        else:
            print(f"❓ {layer_name}: GrhIndex={base_grh} (desconocido)")
            found_any = True
    
    if not found_any:
        print("(Sin objetos en capas interactuables)")
    
    if tile['layer1'] > 0:
        print(f"\n💡 Layer1 (decoración): GrhIndex={tile['layer1']}")
else:
    print("❌ No se pudo leer el tile")

print("=" * 70)
