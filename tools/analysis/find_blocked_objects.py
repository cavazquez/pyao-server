#!/usr/bin/env python3
"""Encuentra objetos en tiles bloqueados que podrían ser puertas."""
import struct
from pathlib import Path
from collections import Counter

def find_blocked_objects(map_path):
    """Encuentra todos los GrhIndex en tiles bloqueados."""
    header_size = 273
    blocked_grh = []
    
    with open(map_path, 'rb') as f:
        f.seek(header_size)
        
        for y in range(1, 101):
            for x in range(1, 101):
                # Leer flags
                flags_data = f.read(1)
                if len(flags_data) != 1:
                    continue
                flags = flags_data[0]
                
                is_blocked = bool(flags & 0x1)
                
                # Layer 1 (ground)
                layer1_data = f.read(2)
                if len(layer1_data) != 2:
                    continue
                
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
                
                # Si está bloqueado, guardar los GrhIndex
                if is_blocked:
                    for layer_name, layer_grh in [("obj1", layer2), ("obj2", layer3)]:
                        if layer_grh > 0:
                            base_grh = layer_grh & 0x7FFF
                            blocked_grh.append({
                                "x": x,
                                "y": y,
                                "grh": base_grh,
                                "layer": layer_name
                            })
    
    return blocked_grh

# Buscar en mapa 1
map_path = Path('/home/cristian/repos/propios/pyao-server/clientes/ArgentumOnline0.13.3-Cliente-Servidor/server/Maps/Mapa1.map')

print("Buscando objetos en tiles bloqueados del Mapa 1...")
results = find_blocked_objects(map_path)

if results:
    print(f"\n✓ Encontrados {len(results)} objetos en tiles bloqueados")
    
    # Contar frecuencia de GrhIndex
    grh_counter = Counter(r['grh'] for r in results)
    
    print("\nGrhIndex más comunes (podrían ser puertas, paredes, etc.):")
    for grh, count in grh_counter.most_common(20):
        # Mostrar ejemplos de coordenadas
        examples = [r for r in results if r['grh'] == grh][:3]
        coords = ", ".join([f"({r['x']},{r['y']})" for r in examples])
        print(f"  GrhIndex {grh:5d}: {count:3d} veces - Ej: {coords}")
else:
    print("\n✗ No se encontraron objetos en tiles bloqueados")
