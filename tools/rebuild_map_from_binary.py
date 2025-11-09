#!/usr/bin/env python3
"""
Script para reconstruir el JSON de objetos del mapa basado en datos binarios
Analiza el mapa binario y extrae árboles, yacimientos y otros objetos
"""
import struct
import json
import os
import re
import tomllib
from pathlib import Path

def load_grh_to_objtype_mapping():
    """Carga el mapeo de GrhIndex a ObjType desde archivos TOML"""
    grh_to_objtype = {}
    data_dir = Path('/home/cristian/repos/propios/pyao-server/data/items')
    
    for toml_file in data_dir.rglob('*.toml'):
        try:
            with open(toml_file, 'rb') as f:
                data = tomllib.load(f)
            
            if 'item' in data:
                for item in data['item']:
                    grh_index = item.get('GrhIndex')
                    obj_type = item.get('ObjType')
                    
                    if grh_index is not None and obj_type is not None:
                        grh_to_objtype[grh_index] = obj_type
        except Exception:
            pass  # Ignorar archivos que no se puedan leer
    
    return grh_to_objtype

# Cargar mapeo al inicio
GRH_TO_OBJTYPE = load_grh_to_objtype_mapping()
print(f"📚 Cargados {len(GRH_TO_OBJTYPE)} GrhIndex → ObjType mappings")

def read_map_tile(map_path, x, y):
    """Lee los 3 layers de una coordenada específica en el mapa (formato VB6)"""
    try:
        with open(map_path, 'rb') as f:
            # Header de 273 bytes
            header_size = 273
            map_width = 100
            map_height = 100
            bytes_per_tile = 2  # VB6 usa 2 bytes por tile
            
            # Calcular índice del tile (x, y son 1-indexed)
            tile_index = (y - 1) * map_width + (x - 1)
            
            # Leer las 3 layers
            layers = {}
            layer_names = ['ground', 'obj1', 'obj2']
            
            for i, layer_name in enumerate(layer_names):
                layer_offset = header_size + (i * map_width * map_height * bytes_per_tile)
                tile_offset = layer_offset + (tile_index * bytes_per_tile)
                
                f.seek(tile_offset)
                data = f.read(bytes_per_tile)
                
                if len(data) == bytes_per_tile:
                    value = struct.unpack('<H', data)[0]  # H = unsigned short (2 bytes)
                    layers[layer_name] = value
                else:
                    return {'error': f'No se pudo leer el tile en ({x},{y})'}
            
            return layers
            
    except Exception as e:
        return {'error': str(e)}

def extract_sprites_from_tscn(tscn_path):
    """Extrae Sprite2D del Layer3 del archivo .tscn de Godot con sus grh_ids"""
    if not os.path.exists(tscn_path):
        return []
    
    try:
        with open(tscn_path, 'r') as f:
            content = f.read()
        
        # Patrón para encontrar Sprite2D en Layer3
        sprite_pattern = r'\[node name="@Sprite2D@\d+" type="Sprite2D" parent="Layer3"\]\s*position = Vector2\((\d+), (\d+)\)'
        sprites = []
        
        for match in re.finditer(sprite_pattern, content):
            x_pixels = int(match.group(1))
            y_pixels = int(match.group(2))
            
            # Convertir píxeles a coordenadas de tile (cada tile es 32x32)
            # +1 en X porque hay un offset en el sistema de coordenadas
            x_tile = (x_pixels // 32) + 1
            y_tile = y_pixels // 32
            
            # Extraer el grh_id de la textura
            node_section = content[match.end():match.end()+500]
            texture_match = re.search(r'texture = ExtResource\("(\d+)_\w+"\)', node_section)
            grh_id = None
            
            if texture_match:
                texture_id = texture_match.group(1)
                # Buscar el archivo PNG asociado
                ext_pattern = rf'\[ext_resource type="Texture2D" path="[^"]*?(\d+)\.png" id="{texture_id}_\w+"\]'
                ext_match = re.search(ext_pattern, content)
                if ext_match:
                    grh_id = int(ext_match.group(1))
            
            sprites.append((x_tile, y_tile, grh_id))
        
        return sprites
    except Exception as e:
        print(f"  ⚠️  Error leyendo .tscn: {e}")
        return []

def analyze_map_objects(map_path, map_id):
    """Analiza el mapa y extrae objetos del .tscn"""
    objects = []
    
    print(f"Analizando Mapa {map_id}...")
    
    # El archivo .map no contiene objetos, solo tiles gráficos
    # Los objetos están en el .tscn como Sprite2D
    print(f"  ℹ️  Nota: Los objetos están en el archivo .tscn, no en el .map")
    
    # Agregar Sprite2D del .tscn
    tscn_path = f'/home/cristian/repos/propios/pyao-server/clientes/ArgentumOnlineGodot/Maps/Map{map_id}.tscn'
    sprites = extract_sprites_from_tscn(tscn_path)
    
    if sprites:
        print(f"  📦 Encontrados {len(sprites)} Sprite2D en .tscn")
        
        trees_count = 0
        mines_count = 0
        unknown_count = 0
        
        for x, y, grh_id in sprites:
            obj_type_id = None
            obj_type_name = None
            
            if grh_id and grh_id in GRH_TO_OBJTYPE:
                # Usar el mapeo real desde los archivos TOML
                obj_type_id = GRH_TO_OBJTYPE[grh_id]
                
                # Determinar tipo basado en ObjType
                if obj_type_id == 4:  # eOBJType_otArboles
                    obj_type_name = "tree"
                    trees_count += 1
                elif obj_type_id == 36:  # eOBJType_otArbolElfico
                    obj_type_name = "tree"
                    trees_count += 1
                elif obj_type_id == 22:  # eOBJType_otYacimiento
                    obj_type_name = "mine"
                    mines_count += 1
                elif obj_type_id == 38:  # eOBJType_otYacimientoPez
                    obj_type_name = "mine"
                    mines_count += 1
                else:
                    # Tipo conocido pero no es árbol ni yacimiento
                    print(f"  ⚠️  Objeto tipo {obj_type_id} en ({x},{y}) grh_id={grh_id} - ignorando")
                    continue
            elif grh_id:
                # GrhIndex no encontrado en TOML, usar fallback por rangos
                if 6000 <= grh_id <= 7300:
                    obj_type_name = "tree"
                    trees_count += 1
                    print(f"  ⚠️  grh_id {grh_id} en ({x},{y}) no en TOML - asumiendo árbol por rango")
                elif 8600 <= grh_id <= 8700:
                    obj_type_name = "mine"
                    mines_count += 1
                    print(f"  ⚠️  grh_id {grh_id} en ({x},{y}) no en TOML - asumiendo yacimiento por rango")
                else:
                    unknown_count += 1
                    print(f"  ⚠️  grh_id {grh_id} en ({x},{y}) desconocido - ignorando")
                    continue
            else:
                # Sin grh_id
                unknown_count += 1
                print(f"  ⚠️  Sin grh_id en ({x},{y}) - ignorando")
                continue
            
            obj = {
                "t": obj_type_name,
                "x": x,
                "y": y,
                "g": grh_id,
                "m": map_id
            }
            objects.append(obj)
            print(f"  ✅ {obj_type_name} en ({x},{y}) - grh_id: {grh_id} (desde .tscn)")
        
        print(f"  📊 Total: {len(objects)} objetos ({trees_count} árboles, {mines_count} yacimientos, {unknown_count} ignorados)")
    else:
        print(f"  ⚠️  No se encontraron Sprite2D en el .tscn")
    
    return objects

def rebuild_all_maps():
    """Reconstruye el JSON de todos los mapas (1-290) basado en archivos .tscn"""
    
    # Definir rangos de archivos
    ranges = [
        (1, 50, 'objects_001-050.json'),
        (51, 100, 'objects_051-100.json'),
        (101, 150, 'objects_101-150.json'),
        (151, 200, 'objects_151-200.json'),
        (201, 250, 'objects_201-250.json'),
        (251, 290, 'objects_251-290.json')
    ]
    
    for start_map, end_map, filename in ranges:
        objects_file = f'/home/cristian/repos/propios/pyao-server/map_data/{filename}'
        backup_file = objects_file + '.backup'
        
        print(f"\n{'='*60}")
        print(f"Procesando mapas {start_map}-{end_map} → {filename}")
        print(f"{'='*60}")
        
        # Hacer backup del archivo original si existe
        if os.path.exists(objects_file):
            print(f"📁 Creando backup: {backup_file}")
            with open(objects_file, 'r') as src, open(backup_file, 'w') as dst:
                dst.write(src.read())
        
        all_objects = []
        total_trees = 0
        total_mines = 0
        
        # Procesar cada mapa en el rango
        for map_id in range(start_map, end_map + 1):
            # Analizar mapa
            map_path = f'/home/cristian/repos/propios/pyao-server/clientes/ArgentumOnline0.13.3-Cliente-Servidor/server/Maps/Mapa{map_id}.map'
            new_objects = analyze_map_objects(map_path, map_id)
            
            if new_objects:
                all_objects.extend(new_objects)
                tree_count = sum(1 for obj in new_objects if obj['t'] == 'tree')
                mine_count = sum(1 for obj in new_objects if obj['t'] == 'mine')
                total_trees += tree_count
                total_mines += mine_count
        
        print(f"\n📊 Resumen {start_map}-{end_map}:")
        print(f"   - Total objetos: {len(all_objects)}")
        print(f"   - Total árboles: {total_trees}")
        print(f"   - Total yacimientos: {total_mines}")
        
        # Escribir nuevo archivo JSON
        with open(objects_file, 'w') as f:
            for obj in all_objects:
                f.write(json.dumps(obj) + '\n')
        
        print(f"✅ Archivo generado: {objects_file}")
    
    print(f"\n{'='*60}")
    print(f"🎉 TODOS LOS MAPAS RECONSTRUIDOS EXITOSAMENTE")
    print(f"{'='*60}")
    print(f"\n🎯 Para revertir cambios, restaura los backups:")
    print(f"   cp map_data/*.backup map_data/")
    
    # Analizar mapa binario
    new_objects = analyze_map_objects(map_path, map_id)
    
    print(f"\n📊 Resumen del análisis:")
    print(f"   - Objetos encontrados: {len(new_objects)}")
    
    # Contar por tipo
    tree_count = sum(1 for obj in new_objects if obj['t'] == 'tree')
    mine_count = sum(1 for obj in new_objects if obj['t'] == 'mine')
    
    print(f"   - Árboles: {tree_count}")
    print(f"   - Yacimientos: {mine_count}")
    
    # Leer objetos existentes de otros mapas
    other_map_objects = []
    if os.path.exists(objects_file):
        with open(objects_file, 'r') as f:
            for line in f:
                obj = json.loads(line.strip())
                if obj['m'] != map_id:  # Mantener objetos de otros mapas
                    other_map_objects.append(obj)
    
    print(f"   - Objetos de otros mapas preservados: {len(other_map_objects)}")
    
    # Generar nuevo archivo JSON
    temp_file = objects_file + '.tmp'
    with open(temp_file, 'w') as f:
        # Escribir objetos de otros mapas primero
        for obj in other_map_objects:
            f.write(json.dumps(obj) + '\n')
        
        # Escribir nuevos objetos del mapa analizado
        for obj in new_objects:
            f.write(json.dumps(obj) + '\n')
    
    # Reemplazar archivo original
    os.replace(temp_file, objects_file)
    
    print(f"\n✅ Mapa {map_id} reconstruido exitosamente:")
    print(f"   - Archivo actualizado: {objects_file}")
    print(f"   - Backup creado: {backup_file}")
    print(f"   - Total de objetos en archivo: {len(other_map_objects) + len(new_objects)}")
    
    # Verificación específica de las coordenadas problemáticas
    print(f"\n🔍 Verificación de coordenadas específicas:")
    test_coords = [(23, 31), (23, 28), (64, 66), (50, 75), (50, 76), (53, 77), (3, 1), (75, 2), (81, 2), (92, 3)]
    
    for x, y in test_coords:
        found = None
        for obj in new_objects:
            if obj['x'] == x and obj['y'] == y:
                found = obj
                break
        
        if found:
            print(f"   ({x},{y}): {found['t']} (grh_id={found['g']}) ✅")
        else:
            print(f"   ({x},{y}): [vacío] ✅")

def compare_with_original(map_id=50):
    """Compara el JSON reconstruido con los datos binarios"""
    map_path = f'/home/cristian/repos/propios/pyao-server/clientes/ArgentumOnlineGodot/Assets/Maps/mapa{map_id}.map'
    objects_file = f'/home/cristian/repos/propios/pyao-server/map_data/objects_001-050.json'
    
    print(f"\n🔬 Comparación final para Mapa {map_id}:")
    
    # Cargar objetos del JSON
    json_objects = {}
    if os.path.exists(objects_file):
        with open(objects_file, 'r') as f:
            for line in f:
                obj = json.loads(line.strip())
                if obj['m'] == map_id:
                    json_objects[(obj['x'], obj['y'])] = obj
    
    print(f"   Objetos en JSON: {len(json_objects)}")
    
    # Verificar coordenadas específicas
    test_coords = [(23, 31), (23, 28), (64, 66), (50, 75), (50, 76), (53, 77), (3, 1), (75, 2), (81, 2), (92, 3)]
    
    for x, y in test_coords:
        tiles = read_map_tile(map_path, x, y)
        
        if 'error' in tiles:
            print(f"   ({x},{y}): ERROR leyendo mapa binario")
            continue
        
        # Determinar qué debería haber según el binario (usando misma lógica de patrones)
        expected = None
        for layer_name, grh_value in tiles.items():
            obj_type = None
            grh_id = None
            is_valid_object = False
            
            # Extraer grh_id base si tiene flags
            if grh_value >= 25000:  # Con flags
                base_grh = grh_value & 0x7FFF
                flag = grh_value & 0x8000
                
                # Árboles - excluir grh_ids problemáticos globalmente
                if 7000 <= base_grh <= 7020 and map_id != 50:
                    if base_grh not in [7001]:  # EXCLUIR falsos árboles
                        if layer_name in ['obj2', 'obj1'] and base_grh in [7000, 7002]:
                            obj_type = 'tree'
                            grh_id = base_grh
                            is_valid_object = True
                
                # Yacimientos - excluir patrones problemáticos globalmente
                elif 8600 <= base_grh <= 8700:
                    if layer_name in ['obj2', 'obj1']:
                        # EXCLUIR patrones falsos
                        if not (base_grh == 8616 and layer_name == 'obj1') and \
                           not (base_grh == 8617 and layer_name == 'obj2'):
                            obj_type = 'mine'
                            grh_id = base_grh
                            is_valid_object = True
                
                # Casos especiales
                elif grh_value == 32769:  # yacimiento confirmado
                    # Excluir en coordenadas problemáticas
                    if (x, y) not in [(75, 2), (81, 2)]:
                        obj_type = 'mine'
                        grh_id = 8616
                        is_valid_object = True
                # EXCLUIR falsos árboles globalmente
                elif grh_value == 30721 or grh_value == 28673:
                    continue
                    
            else:  # Sin flags
                # Árboles sin flags
                if 7000 <= grh_value <= 7020 and map_id != 50:
                    if grh_value not in [7001]:  # EXCLUIR falsos árboles
                        if layer_name in ['obj2', 'obj1'] and grh_value in [7000, 7002]:
                            obj_type = 'tree'
                            grh_id = grh_value
                            is_valid_object = True
                
                # Yacimientos sin flags - excluir patrones problemáticos
                elif 8600 <= grh_value <= 8700:
                    if layer_name in ['obj2', 'obj1']:
                        # EXCLUIR patrones falsos globalmente
                        # grh_id 8617 en layer obj2 es siempre falso
                        if not (grh_value == 8617 and layer_name == 'obj2'):
                            obj_type = 'mine'
                            grh_id = grh_value
                            is_valid_object = True
            
            if is_valid_object and obj_type and grh_id:
                expected = (obj_type, grh_id)
                break  # Encontramos objeto válido, salir del loop
        
        # Verificar JSON
        json_obj = json_objects.get((x, y))
        
        if expected and json_obj:
            if json_obj['t'] == expected[0]:
                print(f"   ({x},{y}): ✅ {json_obj['t']} (coincide)")
            else:
                print(f"   ({x},{y}): ❌ JSON={json_obj['t']}, BINARIO={expected[0]}")
        elif expected and not json_obj:
            print(f"   ({x},{y}): ❌ Faltante en JSON (debería ser {expected[0]})")
        elif not expected and json_obj:
            print(f"   ({x},{y}): ❌ Sobrante en JSON (hay {json_obj['t']})")
        else:
            print(f"   ({x},{y}): ✅ Vacío (coincide)")

def main():
    print("=== RECONSTRUCTOR DE MAPAS DESDE BINARIO ===")
    
    # Reconstruir mapa 50
    rebuild_map_json(50)
    
    # Comparar resultados
    compare_with_original(50)
    
    print(f"\n🎯 Para revertir cambios, restaura el backup:")
    print(f"   cp map_data/objects_001-050.json.backup map_data/objects_001-050.json")

if __name__ == '__main__':
    print("=== RECONSTRUCTOR DE MAPAS DESDE .TSCN ===")
    rebuild_all_maps()
