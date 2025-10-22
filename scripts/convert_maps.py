#!/usr/bin/env python3
"""
Convertidor de mapas binarios de Argentum Online a JSON

Este script convierte los archivos .map del cliente de AO a archivos JSON organizados
siguiendo la estructura:

map_data/
└── 001_map.json           # Archivo JSON con todos los datos del mapa
"""

import struct
import json
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional
import re

# Configuración
MAPS_SOURCE_DIR = Path("clientes/ArgentumOnline0.13.3-Cliente-Servidor/client/Mapas")
MAPS_OUTPUT_DIR = Path("map_data")

# Rangos de gráficos de agua (para detección automática)
WATER_RANGES = [
    (1505, 1520),    # Agua tipo 1
    (5665, 5680),    # Agua tipo 2
    (13547, 13562),  # Agua tipo 3
]

# Tamaño del mapa (en tiles)
MAP_WIDTH = 100
MAP_HEIGHT = 100


def is_water(grh_index: int) -> bool:
    """Determina si un gráfico es agua basado en su índice."""
    return any(min_val <= grh_index <= max_val for min_val, max_val in WATER_RANGES)


def parse_map_file(map_path: Path, debug: bool = False) -> Optional[Dict[str, Any]]:
    """
    Parsea un archivo .map de Argentum Online.
    
    Args:
        map_path: Ruta al archivo .map
        debug: Si es True, muestra información de depuración detallada
        
    Returns:
        Dict con la estructura del mapa o None en caso de error
    """
    try:
        # Verificar tamaño del archivo
        file_size = map_path.stat().st_size
        expected_size = 4 + 100 + 4 + 8 + (100 * 100 * 3)  # cabecera + clima + temporales + celdas
        
        if file_size < expected_size:
            print(f"  ✗ Archivo demasiado pequeño: {map_path.name} ({file_size} bytes, se esperaban al menos {expected_size} bytes)")
            return None
            
        # Si el archivo es más grande de lo esperado, mostrar advertencia pero continuar
        if file_size > expected_size:
            print(f"  ⚠️  Advertencia: {map_path.name} es más grande de lo esperado ({file_size} bytes, se esperaban {expected_size} bytes)")
            
        with open(map_path, 'rb') as f:
            data = f.read()
            
        if debug:
            print(f"\n=== Información de depuración para {map_path.name} ===")
            print(f"Tamaño del archivo: {len(data)} bytes")
            print("Primeros 32 bytes:", data[:32].hex(' '))
            
    except IOError as e:
        print(f"  ✗ Error al leer {map_path.name}: {e}")
        return None
    
    offset = 0
    result = {
        'metadata': {
            'version': 0,
            'header': '',
            'llueve': 0,    # Lluvia
            'nieba': 0,     # Nieve
        },
        'ground': [[0] * MAP_WIDTH for _ in range(MAP_HEIGHT)],
        'objects': [[0] * MAP_WIDTH for _ in range(MAP_HEIGHT)],
        'upper': {'sprites': []},
        'graphics': {'sprites': []},
        'flags': [[0] * MAP_WIDTH for _ in range(MAP_HEIGHT)],
        'triggers': []
    }
    
    try:
        # 1. Leer versión del mapa (2 bytes, little-endian)
        result['metadata']['version'] = struct.unpack('<H', data[offset:offset+2])[0]
        offset += 2
        
        # 2. Leer cabecera (100 bytes, string terminado en null)
        header = data[offset:offset+100].split(b'\x00')[0].decode('latin-1', errors='ignore')
        result['metadata']['header'] = header.strip()
        offset += 100
        
        # 3. Leer clima (2 bytes cada uno, little-endian)
        result['metadata']['llueve'] = struct.unpack('<H', data[offset:offset+2])[0]  # Lluvia
        offset += 2
        result['metadata']['nieba'] = struct.unpack('<H', data[offset:offset+2])[0]   # Nieve
        offset += 2
        
        # 4. Saltar campos temporales (4 * 2 bytes = 8 bytes)
        offset += 8
        
        # 5. Procesar cada celda del mapa (100x100)
        for y in range(MAP_HEIGHT):
            for x in range(MAP_WIDTH):
                # Verificar si hay suficientes datos restantes para los campos mínimos (flags + graphic1)
                if offset + 3 > len(data):
                    print(f"  ✗ Error: Se alcanzó el final del archivo inesperadamente en la celda ({x}, {y})")
                    print(f"  Tamaño restante: {len(data) - offset} bytes")
                    print(f"  Se esperaban al menos 3 bytes (flags + graphic1) en la posición {offset}")
                    print(f"  Últimos 16 bytes del archivo: {data[-16:].hex(' ')}" if len(data) > 0 else "  El archivo está vacío")
                    return None
                    
                try:
                    # 5.1 Leer flags del tile (1 byte)
                    by_flags = data[offset]
                    offset += 1
                    
                    # 5.2 Leer gráfico de la capa base (siempre presente, 2 bytes)
                    graphic1 = struct.unpack('<H', data[offset:offset+2])[0]
                    offset += 2
                    result['ground'][y][x] = graphic1
                
                except struct.error as e:
                    print(f"  ✗ Error al leer la celda ({x}, {y}): {e}")
                    print(f"  Offset: {offset}, Bytes restantes: {len(data) - offset}")
                    print(f"  Bytes disponibles: {data[offset:min(offset+16, len(data))].hex(' ')}...")
                    print(f"  Flag byte: 0x{by_flags:02x} (bin: {by_flags:08b})" if 'by_flags' in locals() else "  No se pudo leer el byte de flags")
                    return None
                    
                try:
                    # 5.3 Marcar como bloqueado si corresponde
                    if by_flags & 0x01:  # Bit 0: Bloqueado
                        result['flags'][y][x] = 1
                    
                    # 5.4 Leer capa de objetos (opcional, 2 bytes)
                    if by_flags & 0x02:  # Bit 1: Tiene objeto
                        if offset + 2 > len(data):
                            print(f"  ✗ Error: Se esperaban 2 bytes para el objeto en ({x}, {y})")
                            return None
                        graphic2 = struct.unpack('<H', data[offset:offset+2])[0]
                        offset += 2
                        result['objects'][y][x] = graphic2
                    
                    # 5.5 Leer capa superior (opcional, 2 bytes)
                    if by_flags & 0x04:  # Bit 2: Tiene capa superior
                        if offset + 2 > len(data):
                            print(f"  ✗ Error: Se esperaban 2 bytes para la capa superior en ({x}, {y})")
                            return None
                        graphic3 = struct.unpack('<H', data[offset:offset+2])[0]
                        offset += 2
                        result['upper']['sprites'].append({
                            'x': x,
                            'y': y,
                            'grh_id': graphic3
                        })
                    
                    # 5.6 Leer triggers (opcional, 1 byte)
                    if by_flags & 0x08:  # Bit 3: Tiene trigger
                        if offset + 1 > len(data):
                            print(f"  ✗ Error: Se esperaba 1 byte para el trigger en ({x}, {y})")
                            return None
                        trigger_type = data[offset]
                        offset += 1
                        result['triggers'].append({
                            'x': x,
                            'y': y,
                            'type': trigger_type
                        })
                    
                    # 5.7 Leer gráficos adicionales (opcional, 2 bytes)
                    if by_flags & 0x10:  # Bit 4: Tiene gráfico adicional
                        if offset + 2 > len(data):
                            print(f"  ✗ Error: Se esperaban 2 bytes para el gráfico adicional en ({x}, {y})")
                            return None
                        graphic4 = struct.unpack('<H', data[offset:offset+2])[0]
                        offset += 2
                        result['graphics']['sprites'].append({
                            'x': x,
                            'y': y,
                            'grh_id': graphic4
                        })
                    
                    # 5.8 Leer partículas (opcional, 2 bytes)
                    if by_flags & 0x20:  # Bit 5: Tiene partículas
                        if offset + 2 > len(data):
                            print(f"  ⚠️  Se esperaban 2 bytes para partículas en ({x}, {y}), pero se alcanzó el final del archivo")
                            # En lugar de break, simplemente salimos de la función con el error
                            print(f"  ✗ Error: Archivo de mapa incompleto o corrupto en ({x}, {y})")
                            return None
                        offset += 2
                    
                    # 5.9 Leer luces (opcional, 2 bytes)
                    if by_flags & 0x40:  # Bit 6: Tiene luces
                        if offset + 2 > len(data):
                            print(f"  ⚠️  Se esperaban 2 bytes para luces en ({x}, {y}), pero se alcanzó el final del archivo")
                            # En lugar de break, simplemente salimos de la función con el error
                            print(f"  ✗ Error: Archivo de mapa incompleto o corrupto en ({x}, {y})")
                            return None
                        offset += 2
                        
                except Exception as e:
                    print(f"  ✗ Error al procesar la celda ({x}, {y}): {e}")
                    print(f"  Tipo de error: {type(e).__name__}")
                    if debug:
                        import traceback
                        traceback.print_exc()
                    return None      
        return result
    
    except struct.error as e:
        print(f"  ✗ Error de formato en {map_path.name} en offset {offset}: {e}")
        print(f"  Tamaño del archivo: {len(data)} bytes, offset actual: {offset}")
        if debug:
            print(f"  Bytes alrededor del error: {data[max(0, offset-16):offset+16].hex(' ')}")
        return None
    except IndexError as e:
        print(f"  ✗ Error de índice en {map_path.name} en offset {offset}")
        print(f"  Tamaño del archivo: {len(data)} bytes, offset actual: {offset}")
        if debug:
            print(f"  Bytes alrededor del error: {data[max(0, offset-16):min(len(data), offset+16)].hex(' ')}")
            print(f"  Últimos 32 bytes del archivo: {data[-32:].hex(' ')}")
        return None
    except Exception as e:
        print(f"  ✗ Error inesperado al procesar {map_path.name}: {e}")
        print(f"  Tipo de error: {type(e).__name__}")
        if debug:
            import traceback
            traceback.print_exc()
        return None


def save_map_components(map_data: Dict[str, Any], output_dir: Path, map_id: int) -> bool:
    """
    Guarda los datos del mapa en múltiples archivos JSON, uno por componente.
    
    Args:
        map_data: Datos del mapa a guardar
        output_dir: Directorio de salida
        map_id: ID numérico del mapa
        
    Returns:
        bool: True si se guardó correctamente, False en caso contrario
    """
    try:
        # Crear directorio de salida si no existe
        output_dir.mkdir(parents=True, exist_ok=True)
        map_prefix = f"{map_id:03d}"
        
        # 1. Guardar metadatos del mapa
        metadata = {
            "id": map_id,
            "name": map_data['metadata']['header'] or f'Mapa {map_id}',
            "width": MAP_WIDTH,
            "height": MAP_HEIGHT,
            "weather": {
                "rain": bool(map_data['metadata']['llueve']),
                "snow": bool(map_data['metadata']['nieba'])
            }
        }
        _save_json_file(output_dir / f"{map_prefix}_metadata.json", metadata)
        
        # 2. Guardar capa de suelo (ground)
        _save_json_file(output_dir / f"{map_prefix}_ground.json", map_data['ground'])
        
        # 3. Guardar capa de objetos (objects)
        _save_json_file(output_dir / f"{map_prefix}_objects.json", map_data['objects'])
        
        # 4. Guardar capa superior (upper)
        upper_data = [{
            "x": sprite['x'],
            "y": sprite['y'],
            "grh_id": sprite['grh_id']
        } for sprite in map_data['upper']['sprites']]
        _save_json_file(output_dir / f"{map_prefix}_upper.json", upper_data)
        
        # 5. Guardar gráficos (graphics)
        graphics_data = [{
            "x": sprite['x'],
            "y": sprite['y'],
            "grh_id": sprite['grh_id']
        } for sprite in map_data['graphics']['sprites']]
        _save_json_file(output_dir / f"{map_prefix}_graphics.json", graphics_data)
        
        # 6. Guardar flags
        _save_json_file(output_dir / f"{map_prefix}_flags.json", map_data['flags'])
        
        # 7. Guardar triggers
        triggers_data = [{
            "x": trigger['x'],
            "y": trigger['y'],
            "type": trigger['type'],
            "description": {
                1: "Zona segura",
                2: "Portal/Exit",
                3: "Zona de tiendas",
                4: "Zona de inicio",
                5: "Mensaje al pisar",
                6: "Trampa"
            }.get(trigger['type'], "Desconocido")
        } for trigger in map_data['triggers']]
        _save_json_file(output_dir / f"{map_prefix}_triggers.json", triggers_data)
        
        # 8. Guardar tiles bloqueados
        blocked_tiles = []
        for y in range(MAP_HEIGHT):
            for x in range(MAP_WIDTH):
                if map_data['flags'][y][x] == 1:  # Bloqueado
                    blocked_tiles.append({"x": x, "y": y, "type": "blocked"})
                elif map_data['flags'][y][x] == 2:  # Agua
                    blocked_tiles.append({"x": x, "y": y, "type": "water"})
        _save_json_file(output_dir / f"{map_prefix}_blocked.json", blocked_tiles)
        
        return True
    
    except Exception as e:
        print(f"Error al guardar componentes del mapa {map_id}: {e}")
        if 'debug' in map_data.get('metadata', {}):
            import traceback
            traceback.print_exc()
        return False


def _save_json_file(file_path: Path, data: Any) -> bool:
    """
    Guarda datos en un archivo JSON con formato legible.
    
    Args:
        file_path: Ruta del archivo de salida
        data: Datos a guardar
        
    Returns:
        bool: True si se guardó correctamente, False en caso contrario
    """
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Error al guardar {file_path}: {e}")
        return False


def get_map_id_from_filename(filename: str) -> Optional[int]:
    """Extrae el ID numérico del mapa a partir del nombre de archivo."""
    match = re.search(r'\d+', filename)
    return int(match.group()) if match else None


def main():
    """Función principal del script."""
    import sys
    
    # Verificar si se proporcionó un archivo específico para depuración
    debug_file = None
    if len(sys.argv) > 1 and not sys.argv[1].startswith('-'):
        debug_file = sys.argv[1]
        print(f"Modo depuración: Procesando solo {debug_file}")
        map_files = [Path(debug_file)]
    else:
        # Procesar todos los archivos .map
        map_files = list(MAPS_SOURCE_DIR.glob("Mapa*.map"))
    
    total_maps = len(map_files)
    success_count = 0
    
    print(f"Iniciando conversión de {total_maps} mapas...")
    
    for map_path in sorted(map_files):
        map_id = get_map_id_from_filename(map_path.name)
        if map_id is None:
            print(f"  ✗ No se pudo obtener el ID del mapa: {map_path.name}")
            continue
            
        print(f"Procesando {map_path.name} (ID: {map_id})...")
        
        # Parsear el archivo .map
        map_data = parse_map_file(map_path, debug=debug_file is not None)
        if map_data is None:
            print("  ✗ Error al parsear el archivo")
            continue
        
        # Crear directorio para este mapa
        map_dir = MAPS_OUTPUT_DIR / f"{map_id:03d}"
        
        # Guardar los componentes del mapa en archivos separados
        if save_map_components(map_data, map_dir, map_id):
            success_count += 1
            print(f"  ✓ Convertido a JSON en {map_dir}/")
        else:
            print(f"  ✗ Error al guardar los archivos JSON en {map_dir}/")
    
    print(f"\nConversión completada: {success_count}/{total_maps} mapas convertidos exitosamente")
    if success_count < total_maps:
        print(f"  - {total_maps - success_count} mapas con errores")


if __name__ == "__main__":
    main()
