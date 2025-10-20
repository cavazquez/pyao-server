"""Parser de archivos .map de Argentum Online.

Basado en el código del cliente Godot en game_assets.gd
"""

import json
import struct
from pathlib import Path


def parse_map_file(map_path: Path) -> dict:
    """Parsea un archivo .map de Argentum Online.
    
    Formato del archivo:
    - Header: 2 + 255 + 4 + 4 + 8 = 273 bytes
    - Tiles: 100x100 tiles, cada uno con:
      - flags (u8): bit 0x1 = blocked
      - layer1 (u16)
      - layer2 (u16) si flags & 0x2
      - layer3 (u16) si flags & 0x4
      - layer4 (u16) si flags & 0x8
      - trigger (u16) si flags & 0x10
    
    Args:
        map_path: Ruta al archivo .map
    
    Returns:
        Diccionario con información del mapa
    """
    blocked_tiles = []
    water_tiles = []
    
    with map_path.open('rb') as f:
        # Saltar header (273 bytes)
        f.seek(2 + 255 + 4 + 4 + 8)
        
        # Leer 100x100 tiles
        for y in range(100):
            for x in range(100):
                # Leer flags
                flags_byte = f.read(1)
                if not flags_byte:
                    break
                flags = struct.unpack('B', flags_byte)[0]
                
                # Layer 1 (siempre presente)
                layer1_bytes = f.read(2)
                if not layer1_bytes:
                    break
                layer1 = struct.unpack('<H', layer1_bytes)[0]
                
                # Verificar si está bloqueado (bit 0x1)
                if flags & 0x1:
                    blocked_tiles.append({"x": x + 1, "y": y + 1, "type": "wall"})
                
                # Layer 2 (si flags & 0x2)
                layer2 = 0
                if flags & 0x2:
                    layer2_bytes = f.read(2)
                    if layer2_bytes:
                        layer2 = struct.unpack('<H', layer2_bytes)[0]
                
                # Layer 3 (si flags & 0x4)
                if flags & 0x4:
                    f.read(2)  # Saltar layer3
                
                # Layer 4 (si flags & 0x8)
                if flags & 0x8:
                    f.read(2)  # Saltar layer4
                
                # Trigger (si flags & 0x10)
                if flags & 0x10:
                    f.read(2)  # Saltar trigger
                
                # Detectar agua (rangos específicos de gráficos)
                is_water = False
                if layer2 == 0:
                    if (1505 <= layer1 <= 1520) or \
                       (5665 <= layer1 <= 5680) or \
                       (13547 <= layer1 <= 13562):
                        is_water = True
                        water_tiles.append({"x": x + 1, "y": y + 1, "type": "water"})
    
    return {
        "blocked_tiles": blocked_tiles,
        "water_tiles": water_tiles
    }


def extract_map_data(map_id: int, maps_dir: str = "./clientes/ArgentumOnlineGodot/Assets/Maps") -> dict | None:
    """Extrae datos de un mapa específico.
    
    Args:
        map_id: ID del mapa
        maps_dir: Directorio con archivos .map
    
    Returns:
        Diccionario con datos del mapa o None si no existe
    """
    map_path = Path(maps_dir) / f"mapa{map_id}.map"
    
    if not map_path.exists():
        print(f"⚠️  Mapa {map_id} no encontrado: {map_path}")
        return None
    
    print(f"📖 Parseando mapa{map_id}.map...")
    data = parse_map_file(map_path)
    
    print(f"   ✅ {len(data['blocked_tiles'])} tiles bloqueados")
    print(f"   ✅ {len(data['water_tiles'])} tiles de agua")
    
    return data


def generate_map_json(map_id: int, name: str, map_data: dict) -> dict:
    """Genera estructura JSON para un mapa.
    
    Args:
        map_id: ID del mapa
        name: Nombre del mapa
        map_data: Datos extraídos del .map
    
    Returns:
        Diccionario con estructura del mapa
    """
    # Combinar tiles bloqueados y agua
    all_blocked = map_data['blocked_tiles'] + map_data['water_tiles']
    
    return {
        "id": map_id,
        "name": name,
        "width": 100,
        "height": 100,
        "blocked_tiles": all_blocked,
        "spawn_points": [
            {"x": 50, "y": 50, "description": f"Centro de {name}"}
        ]
    }


def update_all_maps():
    """Actualiza archivos JSON de todos los mapas configurados."""
    maps_dir = Path("maps")
    maps_dir.mkdir(exist_ok=True)
    
    # Mapas configurados en map_transitions.toml
    maps_config = [
        (1, "Ullathorpe"),
        (2, "Bosque Norte"),
        (3, "Campo Sur"),
        (4, "Bosque Este"),
        (5, "Montañas Oeste"),
        (6, "Bosque Profundo"),
        (7, "Camino del Desierto"),
        (8, "Tierras Salvajes"),
        (9, "Paso de Montaña"),
    ]
    
    print("=" * 70)
    print("Parser de Mapas de Argentum Online")
    print("=" * 70)
    print()
    
    for map_id, name in maps_config:
        # Extraer datos del .map
        map_data = extract_map_data(map_id)
        
        if not map_data:
            print(f"   ⚠️  Usando datos vacíos para mapa {map_id}\n")
            map_data = {"blocked_tiles": [], "water_tiles": []}
        
        # Generar JSON
        map_json = generate_map_json(map_id, name, map_data)
        
        # Guardar archivo
        output_file = maps_dir / f"map_{map_id}.json"
        with output_file.open('w', encoding='utf-8') as f:
            json.dump(map_json, f, indent=2, ensure_ascii=False)
        
        total_blocked = len(map_json['blocked_tiles'])
        print(f"   💾 Guardado: {output_file} ({total_blocked} tiles bloqueados)")
        print()
    
    print("=" * 70)
    print(f"✅ {len(maps_config)} mapas actualizados correctamente")
    print("=" * 70)


if __name__ == "__main__":
    update_all_maps()
