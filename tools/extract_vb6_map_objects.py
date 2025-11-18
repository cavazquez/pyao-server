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

def load_object_grh_indices():
    """Carga GrhIndex de todos los objetos interactuables desde TOML"""
    trees = set()
    mines = set()
    anvils = set()
    forges = set()
    signs = set()
    doors = set()
    
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
    
    # Cargar yunques y fraguas
    blacksmith_path = Path(__file__).parent.parent / "data/items/tools/blacksmith.toml"
    if blacksmith_path.exists():
        with open(blacksmith_path, 'rb') as f:
            data = tomllib.load(f)
            for item in data['item']:
                grh = item['GrhIndex']
                obj_type = item.get('ObjType')
                if obj_type == 27:  # Yunque
                    anvils.add(grh)
                elif obj_type == 28:  # Fragua
                    forges.add(grh)
    
    # Cargar carteles
    signs_path = Path(__file__).parent.parent / "data/items/world_objects/signs.toml"
    if signs_path.exists():
        with open(signs_path, 'rb') as f:
            data = tomllib.load(f)
            signs = {item['GrhIndex'] for item in data['item']}
    
    # Cargar puertas
    doors_path = Path(__file__).parent.parent / "data/items/world_objects/doors.toml"
    if doors_path.exists():
        with open(doors_path, 'rb') as f:
            data = tomllib.load(f)
            doors = {item['GrhIndex'] for item in data['item']}
    
    return trees, mines, anvils, forges, signs, doors

def extract_map_objects_vb6(map_path, map_id, tree_grh_set, mine_grh_set, anvil_grh_set, forge_grh_set, sign_grh_set, door_grh_set):
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
                has_blocking_object = False
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
                        has_blocking_object = True
                    
                    # Verificar si es mina
                    elif base_grh in mine_grh_set:
                        objects.append({
                            "m": map_id,
                            "x": x,
                            "y": y,
                            "g": base_grh,
                            "t": "mine"
                        })
                        has_blocking_object = True
                    
                    # Verificar si es yunque
                    elif base_grh in anvil_grh_set:
                        objects.append({
                            "m": map_id,
                            "x": x,
                            "y": y,
                            "g": base_grh,
                            "t": "anvil"
                        })
                        has_blocking_object = True
                    
                    # Verificar si es fragua
                    elif base_grh in forge_grh_set:
                        objects.append({
                            "m": map_id,
                            "x": x,
                            "y": y,
                            "g": base_grh,
                            "t": "forge"
                        })
                        has_blocking_object = True
                    
                    # Verificar si es cartel
                    elif base_grh in sign_grh_set:
                        objects.append({
                            "m": map_id,
                            "x": x,
                            "y": y,
                            "g": base_grh,
                            "t": "sign"
                        })
                        has_blocking_object = True
                    
                    # Verificar si es puerta
                    elif base_grh in door_grh_set:
                        objects.append({
                            "m": map_id,
                            "x": x,
                            "y": y,
                            "g": base_grh,
                            "t": "door"
                        })
                        has_blocking_object = True
                
                # Detectar tiles bloqueados (pero NO si ya es árbol/mina/yunque/fragua)
                if (flags & 0x1) and not has_blocking_object:
                    blocked_tiles.append({
                        "m": map_id,
                        "x": x,
                        "y": y,
                        "t": "b"
                    })
    
    return objects, blocked_tiles


def _generate_compact_metadata(map_ids, maps_dir: Path) -> None:
    """Genera archivos metadata_XXX-YYY.json en formato compacto.

    Cada archivo contiene un mapa por línea con las claves compactas:
    ``i`` (id), ``n`` (nombre), ``w`` (width), ``h`` (height), ``r`` (rain), ``s`` (snow).
    """
    map_ids = sorted(set(map_ids))
    if not map_ids:
        return

    # Eliminar metadatos previos consolidados
    for meta_file in maps_dir.glob("metadata_*.json"):
        meta_file.unlink()

    all_metadata = []
    for map_id in map_ids:
        metadata = {
            "i": map_id,
            "n": f"Mapa {map_id}",
            "w": 100,
            "h": 100,
            "r": False,
            "s": False,
        }
        all_metadata.append(metadata)

    # Generar archivos en lotes de 50 mapas, un mapa por línea
    for i in range(0, len(all_metadata), 50):
        batch = all_metadata[i : i + 50]
        start_id = batch[0]["i"]
        end_id = batch[-1]["i"]

        output_file = maps_dir / f"metadata_{start_id:03d}-{end_id:03d}.json"
        with output_file.open("w", encoding="utf-8") as f:
            for metadata in batch:
                f.write(json.dumps(metadata, separators=(",", ":")) + "\n")

        print(f"  ✅ {output_file.name}: {len(batch)} mapas")

def main():
    print("\n🔍 Extrayendo objetos desde mapas VB6...\n")
    
    # Cargar GrhIndex conocidos
    tree_grh_set, mine_grh_set, anvil_grh_set, forge_grh_set, sign_grh_set, door_grh_set = load_object_grh_indices()
    print(f"📚 Cargados {len(tree_grh_set)} GrhIndex de árboles")
    print(f"📚 Cargados {len(mine_grh_set)} GrhIndex de minas")
    print(f"📚 Cargados {len(anvil_grh_set)} GrhIndex de yunques")
    print(f"📚 Cargados {len(forge_grh_set)} GrhIndex de fraguas")
    print(f"📚 Cargados {len(sign_grh_set)} GrhIndex de carteles")
    print(f"📚 Cargados {len(door_grh_set)} GrhIndex de puertas\n")
    
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
    
    processed_map_ids = set()

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
                    mine_grh_set,
                    anvil_grh_set,
                    forge_grh_set,
                    sign_grh_set,
                    door_grh_set,
                )
                
                all_objects.extend(objects)
                all_blocked.extend(blocked)
                processed_map_ids.add(map_id)
                
                if objects:
                    trees = sum(1 for obj in objects if obj['t'] == 'tree')
                    mines = sum(1 for obj in objects if obj['t'] == 'mine')
                    anvils = sum(1 for obj in objects if obj['t'] == 'anvil')
                    forges = sum(1 for obj in objects if obj['t'] == 'forge')
                    signs = sum(1 for obj in objects if obj['t'] == 'sign')
                    doors = sum(1 for obj in objects if obj['t'] == 'door')
                    
                    parts = []
                    if trees > 0:
                        parts.append(f"{trees:3d} árboles")
                    if mines > 0:
                        parts.append(f"{mines:2d} minas")
                    if anvils > 0:
                        parts.append(f"{anvils:2d} yunques")
                    if forges > 0:
                        parts.append(f"{forges:2d} fraguas")
                    if signs > 0:
                        parts.append(f"{signs:2d} carteles")
                    if doors > 0:
                        parts.append(f"{doors:2d} puertas")
                    
                    if parts:
                        print(f"  Mapa {map_id:3d}: {', '.join(parts)}")
                
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

    # Generar metadatos compactos a partir de los mapas procesados
    if processed_map_ids:
        print("\n🧾 Generando metadatos compactos desde mapas VB6...")
        _generate_compact_metadata(processed_map_ids, output_dir)
    
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
