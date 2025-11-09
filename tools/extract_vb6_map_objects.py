#!/usr/bin/env python3
"""
Extrae objetos (árboles, minas) desde los mapas del servidor VB6 original.
Formato: Usa flags para determinar qué layers están presentes.
"""
import struct
import json
import tomllib
from pathlib import Path
from collections import defaultdict

def load_trees_and_mines_grh():
    """Carga GrhIndex de árboles y minas desde TOML"""
    trees = set()
    mines = set()
    
    # Cargar árboles
    trees_path = Path(__file__).parent.parent / "data/items/world_objects/trees.toml"
    if trees_path.exists():
        with open(trees_path, 'rb') as f:
            data = tomllib.load(f)
            trees = {item['GrhIndex'] for item in data['item']}
    
    # Cargar minas
    mines_path = Path(__file__).parent.parent / "data/items/world_objects/mines.toml"
    if mines_path.exists():
        with open(mines_path, 'rb') as f:
            data = tomllib.load(f)
            mines = {item['GrhIndex'] for item in data['item']}
    
    return trees, mines

def extract_map_objects_vb6(map_path, map_id, tree_grh_set, mine_grh_set):
    """Extrae objetos de un mapa VB6 (formato con flags)"""
    header_size = 273
    objects = []
    blocked_tiles = []
    
    with open(map_path, 'rb') as f:
        # Saltar header
        f.seek(header_size)
        
        for y in range(1, 101):
            for x in range(1, 101):
                # Leer flags (1 byte)
                flags_data = f.read(1)
                if len(flags_data) != 1:
                    continue
                flags = flags_data[0]
                
                # Layer 1 (ground) - siempre presente
                layer1_data = f.read(2)
                if len(layer1_data) != 2:
                    continue
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
                if flags & 0x8:
                    f.read(2)  # Skip layer4
                
                # Trigger - si flag & 0x10
                if flags & 0x10:
                    f.read(2)  # Skip trigger
                
                # Detectar objetos en layer2 y layer3
                has_tree_or_mine = False
                for layer_grh in [layer2, layer3]:
                    if layer_grh == 0:
                        continue
                    
                    base_grh = layer_grh & 0x7FFF
                    
                    # Verificar si es árbol
                    if base_grh in tree_grh_set:
                        objects.append({
                            "m": map_id,
                            "x": x,
                            "y": y,
                            "g": base_grh,
                            "t": "tree"
                        })
                        has_tree_or_mine = True
                    
                    # Verificar si es mina
                    elif base_grh in mine_grh_set:
                        objects.append({
                            "m": map_id,
                            "x": x,
                            "y": y,
                            "g": base_grh,
                            "t": "mine"
                        })
                        has_tree_or_mine = True
                
                # Detectar tiles bloqueados (pero NO si ya es árbol/mina)
                if (flags & 0x1) and not has_tree_or_mine:
                    blocked_tiles.append({
                        "m": map_id,
                        "x": x,
                        "y": y,
                        "t": "b"
                    })
    
    return objects, blocked_tiles

def main():
    print("\n🔍 Extrayendo objetos desde mapas VB6...\n")
    
    # Cargar GrhIndex conocidos
    tree_grh_set, mine_grh_set = load_trees_and_mines_grh()
    print(f"📚 Cargados {len(tree_grh_set)} GrhIndex de árboles")
    print(f"📚 Cargados {len(mine_grh_set)} GrhIndex de minas\n")
    
    # Directorio de mapas VB6
    maps_dir = Path('/home/cristian/repos/propios/pyao-server/clientes/ArgentumOnline0.13.3-Cliente-Servidor/server/Maps')
    output_dir = Path(__file__).parent.parent / 'map_data'
    output_dir.mkdir(exist_ok=True)
    
    # Procesar mapas en rangos
    ranges = [
        (1, 50),
        (51, 100),
        (101, 150),
        (151, 200),
        (201, 250),
        (251, 290)
    ]
    
    for start_map, end_map in ranges:
        all_objects = []
        all_blocked = []
        
        print(f"📁 Procesando mapas {start_map}-{end_map}...")
        
        for map_id in range(start_map, end_map + 1):
            map_file = maps_dir / f"Mapa{map_id}.map"
            
            if not map_file.exists():
                continue
            
            try:
                objects, blocked = extract_map_objects_vb6(
                    str(map_file),
                    map_id,
                    tree_grh_set,
                    mine_grh_set
                )
                
                all_objects.extend(objects)
                all_blocked.extend(blocked)
                
                if objects:
                    trees = sum(1 for obj in objects if obj['t'] == 'tree')
                    mines = sum(1 for obj in objects if obj['t'] == 'mine')
                    print(f"  Mapa {map_id:3d}: {trees:3d} árboles, {mines:2d} minas")
                
            except Exception as e:
                print(f"  ⚠️  Error en mapa {map_id}: {e}")
        
        # Guardar objetos
        if all_objects:
            objects_file = output_dir / f"objects_{start_map:03d}-{end_map:03d}.json"
            with open(objects_file, 'w', encoding='utf-8') as f:
                for obj in all_objects:
                    f.write(json.dumps(obj) + '\n')
            print(f"  ✅ Guardado: {objects_file.name} ({len(all_objects)} objetos)")
        
        # Guardar bloqueados
        if all_blocked:
            blocked_file = output_dir / f"blocked_{start_map:03d}-{end_map:03d}.json"
            with open(blocked_file, 'w', encoding='utf-8') as f:
                for tile in all_blocked:
                    f.write(json.dumps(tile) + '\n')
            print(f"  ✅ Guardado: {blocked_file.name} ({len(all_blocked)} tiles)")
        
        print()
    
    print("✅ Extracción completada!\n")
    
    # Estadísticas finales
    total_objects = sum(1 for f in output_dir.glob('objects_*.json') for _ in open(f))
    total_blocked = sum(1 for f in output_dir.glob('blocked_*.json') for _ in open(f))
    
    print("📊 RESUMEN FINAL")
    print("=" * 70)
    print(f"Total de objetos extraídos: {total_objects}")
    print(f"Total de tiles bloqueados: {total_blocked}")
    print("=" * 70)

if __name__ == "__main__":
    main()
