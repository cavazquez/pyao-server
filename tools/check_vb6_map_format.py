#!/usr/bin/env python3
"""Verifica el formato del mapa VB6 en la coordenada (74, 92)"""
import struct

def read_vb6_map_tile(map_path, x, y):
    """Lee un tile del mapa VB6 (formato binario con flags)"""
    header_size = 273
    map_width = 100
    map_height = 100
    
    with open(map_path, 'rb') as f:
        # Saltar header
        f.seek(header_size)
        
        # Leer tile por tile hasta llegar a (x, y)
        for tile_y in range(1, 101):
            for tile_x in range(1, 101):
                # Leer flags (1 byte)
                flags_data = f.read(1)
                if len(flags_data) != 1:
                    return None
                flags = flags_data[0]
                
                # Layer 1 (ground) - siempre presente
                layer1_data = f.read(2)
                if len(layer1_data) != 2:
                    return None
                layer1 = struct.unpack('<H', layer1_data)[0]
                
                # Layer 2 (obj1) - si flag & 0x2
                layer2 = 0
                if flags & 0x2:
                    layer2_data = f.read(2)
                    if len(layer2_data) == 2:
                        layer2 = struct.unpack('<H', layer2_data)[0]
                
                # Layer 3 (obj2) - si flag & 0x4
                layer3 = 0
                if flags & 0x4:
                    layer3_data = f.read(2)
                    if len(layer3_data) == 2:
                        layer3 = struct.unpack('<H', layer3_data)[0]
                
                # Layer 4 - si flag & 0x8
                layer4 = 0
                if flags & 0x8:
                    layer4_data = f.read(2)
                    if len(layer4_data) == 2:
                        layer4 = struct.unpack('<H', layer4_data)[0]
                
                # Trigger - si flag & 0x10
                if flags & 0x10:
                    f.read(2)  # Skip trigger
                
                # Si es el tile que buscamos, retornar
                if tile_x == x and tile_y == y:
                    return {
                        'flags': flags,
                        'blocked': bool(flags & 0x1),
                        'layer1': layer1,
                        'layer2': layer2,
                        'layer3': layer3,
                        'layer4': layer4,
                    }
    
    return None

# Verificar coordenada (74, 92) en formato VB6
vb6_path = '/home/cristian/repos/propios/pyao-server/clientes/ArgentumOnline0.13.3-Cliente-Servidor/server/Maps/Mapa1.map'
godot_path = '/home/cristian/repos/propios/pyao-server/clientes/ArgentumOnlineGodot/Assets/Maps/mapa1.map'

x, y = 74, 92

print(f"\n🔍 Analizando coordenada ({x},{y}) - Mapa 1\n")
print("=" * 70)

# VB6 format
print("📁 SERVIDOR VB6 (formato con flags)")
print("=" * 70)
tile_vb6 = read_vb6_map_tile(vb6_path, x, y)
if tile_vb6:
    print(f"Flags: 0x{tile_vb6['flags']:02X} (blocked={tile_vb6['blocked']})")
    print(f"Layer1 (ground): {tile_vb6['layer1']}")
    print(f"Layer2 (obj1):   {tile_vb6['layer2']}")
    print(f"Layer3 (obj2):   {tile_vb6['layer3']}")
    print(f"Layer4:          {tile_vb6['layer4']}")
    
    if tile_vb6['layer1'] == 28929:
        print("\n✅ GrhIndex 28929 está en Layer1 (ground)")
    if tile_vb6['layer2'] > 0:
        print(f"\n⚠️  Hay objeto en Layer2: {tile_vb6['layer2']}")
    if tile_vb6['layer3'] > 0:
        print(f"\n⚠️  Hay objeto en Layer3: {tile_vb6['layer3']}")
else:
    print("❌ No se pudo leer el tile")

print("\n" + "=" * 70)
print("📁 CLIENTE GODOT (formato simple)")
print("=" * 70)

# Godot format (simple, sin flags)
def read_godot_tile(map_path, x, y):
    header_size = 273
    map_width = 100
    map_height = 100
    
    with open(map_path, 'rb') as f:
        tile_index = (y - 1) * map_width + (x - 1)
        layers = {}
        
        for i, layer_name in enumerate(['ground', 'obj1', 'obj2']):
            layer_offset = header_size + (i * map_width * map_height * 2)
            tile_offset = layer_offset + (tile_index * 2)
            f.seek(tile_offset)
            data = f.read(2)
            if len(data) == 2:
                layers[layer_name] = struct.unpack('<H', data)[0]
        
        return layers

tile_godot = read_godot_tile(godot_path, x, y)
print(f"Ground: {tile_godot['ground']}")
print(f"Obj1:   {tile_godot['obj1']}")
print(f"Obj2:   {tile_godot['obj2']}")

print("\n" + "=" * 70)
print("💡 CONCLUSIÓN")
print("=" * 70)
if tile_vb6 and tile_godot:
    if tile_vb6['layer1'] == tile_godot['ground']:
        print("✅ Ambos formatos coinciden en ground/layer1")
    if tile_vb6['layer2'] == tile_godot['obj1']:
        print("✅ Ambos formatos coinciden en obj1/layer2")
    
    if tile_vb6['layer1'] == 28929 and tile_vb6['layer2'] == 0:
        print("\n⚠️  El árbol (GrhIndex 28929) está SOLO en ground")
        print("⚠️  NO hay objetos en las capas interactuables")
        print("⚠️  Por diseño del juego original, este árbol NO es talable")
