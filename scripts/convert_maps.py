#!/usr/bin/env python3
"""Convertidor de mapas binarios de Argentum Online a JSON.

Este script convierte los archivos .map del cliente de AO a archivos JSON organizados
siguiendo la estructura:

map_data/
└── 001_map.json           # Archivo JSON con todos los datos del mapa
"""

import json
import re
import struct
import sys
import traceback
from pathlib import Path
from typing import Any, TypedDict

# Configuración
MAPS_SOURCE_DIR = Path("clientes/ArgentumOnline0.13.3-Cliente-Servidor/client/Mapas")
MAPS_OUTPUT_DIR = Path("map_data")

# Constantes
MAP_WIDTH = 100
MAP_HEIGHT = 100

# Rangos de gráficos de agua (para detección automática)
WATER_RANGES = [
    (1505, 1520),  # Agua tipo 1
    (5665, 5680),  # Agua tipo 2
    (13547, 13562),  # Agua tipo 3
]


# Type definitions
class MapMetadata(TypedDict):
    """Metadata for an Argentum Online map.

    Attributes:
        version: Map format version
        header: Map header/name
        llueve: Rain effect intensity
        nieba: Snow effect intensity
    """

    version: int
    header: str
    llueve: int  # Lluvia
    nieba: int  # Nieve


class Sprite(TypedDict):
    """Represents a sprite in the map.

    Attributes:
        x: X coordinate
        y: Y coordinate
        grh_id: Graphic ID from the game's GRH index
    """

    x: int
    y: int
    grh_id: int


class MapData(TypedDict):
    """Complete map data structure for an Argentum Online map.

    Attributes:
        metadata: Map metadata and settings
        ground: 2D array of ground tile graphics
        objects: 2D array of object graphics
        upper: Dictionary of upper layer sprites
        graphics: Dictionary of additional graphics
        flags: 2D array of tile flags
        triggers: List of map triggers and events
    """

    metadata: MapMetadata
    ground: list[list[int]]
    objects: list[list[int]]
    upper: dict[str, list[Sprite]]
    graphics: dict[str, list[Sprite]]
    flags: list[list[int]]
    triggers: list[dict[str, Any]]


def is_water(grh_index: int) -> bool:
    """Determina si un gráfico es agua basado en su índice.

    Args:
        grh_index: Índice del gráfico a verificar

    Returns:
        bool: True si el gráfico es agua, False en caso contrario
    """
    return any(min_val <= grh_index <= max_val for min_val, max_val in WATER_RANGES)


def parse_map_file(map_path: Path, debug: bool = False) -> MapData | None:
    """Parsea un archivo .map de Argentum Online.

    Args:
        map_path: Ruta al archivo .map
        debug: Si es True, muestra información de depuración

    Returns:
        MapData | None: Diccionario con los datos del mapa o None en caso de error
    """
    try:
        with Path(map_path).open("rb") as f:
            data = f.read()
    except OSError as e:
        print(f"  ✗ Error al leer el archivo {map_path}: {e}")
        return None

    return _parse_map_data(data, map_path, debug)


def _parse_map_data(data: bytes, map_path: Path, debug: bool) -> MapData | None:  # noqa: PLR0915,PLR0914
    """Parsea los datos binarios de un mapa de Argentum Online.

    Args:
        data: Datos binarios del mapa
        map_path: Ruta al archivo .map (solo para mensajes de error)
        debug: Si es True, muestra información de depuración

    Returns:
        MapData | None: Diccionario con los datos del mapa o None en caso de error
    """
    try:
        # Verificar tamaño del archivo
        file_size = map_path.stat().st_size
        # cabecera + clima + temporales + celdas
        expected_size = 4 + 100 + 4 + 8 + (100 * 100 * 3)

        if file_size < expected_size:
            error_msg = (
                f"  ✗ Archivo demasiado pequeño: {map_path.name} "
                f"({file_size} bytes, se esperaban al menos {expected_size} bytes)"
            )
            print(error_msg)
            return None

        # Si el archivo es más grande de lo esperado, mostrar advertencia
        if file_size > expected_size:
            warning_msg = (
                f"  ⚠️  Advertencia: {map_path.name} es más grande de lo "
                f"esperado ({file_size} bytes, se esperaban {expected_size} bytes)"
            )
            print(warning_msg)

        with Path(map_path).open("rb") as f:
            data = f.read()

        if debug:
            print(f"\n=== Información de depuración para {map_path.name} ===")
            print(f"Tamaño del archivo: {len(data)} bytes")
            print(f"Primeros 32 bytes: {data[:32].hex(' ')}")

    except OSError as e:
        print(f"  ✗ Error al leer {map_path.name}: {e}")
        if debug:
            traceback.print_exc()
        return None

    offset = 0
    result: MapData = {
        "metadata": {
            "version": 0,
            "header": "",
            "llueve": 0,  # Lluvia
            "nieba": 0,  # Nieve
        },
        "ground": [[0] * MAP_WIDTH for _ in range(MAP_HEIGHT)],
        "objects": [[0] * MAP_WIDTH for _ in range(MAP_HEIGHT)],
        "upper": {"sprites": []},
        "graphics": {"sprites": []},
        "flags": [[0] * MAP_WIDTH for _ in range(MAP_HEIGHT)],
        "triggers": [],
    }

    # Función auxiliar para manejar errores de lectura
    def handle_read_error(error_type: str, message: str, current_offset: int) -> None:
        print(f"  ✗ Error de {error_type} en {map_path.name} en offset {current_offset}: {message}")
        print(f"  Tamaño del archivo: {len(data)} bytes, offset actual: {current_offset}")
        if debug:
            start = max(0, current_offset - 16)
            end = min(len(data), current_offset + 16)
            print(f"  Bytes alrededor del error: {data[start:end].hex(' ')}")
            print(f"  Últimos 32 bytes del archivo: {data[-32:].hex(' ')}")

    # Leer versión del mapa (2 bytes, little-endian)
    if offset + 2 > len(data):
        handle_read_error("formato", "No hay suficientes datos para leer la versión", offset)
        return None

    try:
        result["metadata"]["version"] = struct.unpack("<H", data[offset : offset + 2])[0]
        offset += 2
    except struct.error as e:
        handle_read_error("formato", f"Error al leer la versión: {e}", offset)
        return None

    # Leer cabecera (100 bytes, string terminado en null)
    if offset + 100 > len(data):
        handle_read_error("formato", "No hay suficientes datos para leer la cabecera", offset)
        return None

    try:
        header = data[offset : offset + 100].split(b"\x00")[0].decode("latin-1", errors="ignore")
        result["metadata"]["header"] = header.strip()
        offset += 100
    except (UnicodeDecodeError, IndexError) as e:
        handle_read_error("formato", f"Error al decodificar la cabecera: {e}", offset)
        return None

    # Leer clima (llueve, nieba)
    weather_mapping = [
        ("llueve", 0),  # Default value
        ("nieba", 0),  # Default value
    ]

    for weather_type, _ in weather_mapping:
        if offset + 2 > len(data):
            handle_read_error(
                "formato", f"No hay suficientes datos para leer {weather_type}", offset
            )
            return None
        try:
            value = struct.unpack("<H", data[offset : offset + 2])[0]
            if weather_type == "llueve":
                result["metadata"]["llueve"] = value
            elif weather_type == "nieba":
                result["metadata"]["nieba"] = value
            offset += 2
        except struct.error as e:
            handle_read_error("formato", f"Error al leer {weather_type}: {e}", offset)
            return None

    # Saltar campos temporales (4 * 2 bytes = 8 bytes)
    offset += 8

    # Procesar cada celda del mapa (100x100)
    for y in range(MAP_HEIGHT):
        for x in range(MAP_WIDTH):
            # Verificar si hay suficientes datos para los campos mínimos (flags + graphic1)
            if offset + 3 > len(data):
                handle_read_error(
                    "formato",
                    f"Fin de archivo inesperado en celda ({x}, {y}). "
                    f"Se esperaban al menos 3 bytes (flags + graphic1)",
                    offset,
                )
                return None

            # Leer flags del tile (1 byte)
            by_flags = data[offset]
            offset += 1

            # Leer gráfico de la capa base (siempre presente, 2 bytes)
            try:
                graphic1 = struct.unpack("<H", data[offset : offset + 2])[0]
                offset += 2
                result["ground"][y][x] = graphic1
            except struct.error as e:
                handle_read_error(
                    "formato", f"Error al leer el gráfico base en celda ({x}, {y}): {e}", offset
                )
                return None

            # Marcar como bloqueado si corresponde
            if by_flags & 0x01:  # Bit 0: Bloqueado
                result["flags"][y][x] = 1

            # Leer capa de objetos (opcional, 2 bytes)
            if by_flags & 0x02:  # Bit 1: Tiene objeto
                if offset + 2 > len(data):
                    handle_read_error(
                        "formato", f"Faltan 2 bytes para el objeto en ({x}, {y})", offset
                    )
                    return None
                try:
                    graphic2 = struct.unpack("<H", data[offset : offset + 2])[0]
                    offset += 2
                    result["objects"][y][x] = graphic2
                except struct.error as e:
                    handle_read_error(
                        "formato", f"Error al leer el objeto en ({x}, {y}): {e}", offset
                    )
                    return None

            # Leer capa superior (opcional, 2 bytes)
            if by_flags & 0x04:  # Bit 2: Tiene capa superior
                if offset + 2 > len(data):
                    handle_read_error(
                        "formato", f"Faltan 2 bytes para la capa superior en ({x}, {y})", offset
                    )
                    return None
                try:
                    graphic3 = struct.unpack("<H", data[offset : offset + 2])[0]
                    offset += 2
                    result["upper"]["sprites"].append({"x": x, "y": y, "grh_id": graphic3})
                except struct.error as e:
                    handle_read_error(
                        "formato", f"Error al leer la capa superior en ({x}, {y}): {e}", offset
                    )
                    return None

            # Leer triggers (opcional, 1 byte)
            if by_flags & 0x08:  # Bit 3: Tiene trigger
                if offset + 1 > len(data):
                    handle_read_error(
                        "formato", f"Falta 1 byte para el trigger en ({x}, {y})", offset
                    )
                    return None
                trigger_type = data[offset]
                offset += 1
                result["triggers"].append({"x": x, "y": y, "type": trigger_type})

            # Leer gráficos adicionales (opcional, 2 bytes)
            if by_flags & 0x10:  # Bit 4: Tiene gráfico adicional
                if offset + 2 > len(data):
                    handle_read_error(
                        "formato", f"Faltan 2 bytes para el gráfico adicional en ({x}, {y})", offset
                    )
                    return None
                try:
                    graphic4 = struct.unpack("<H", data[offset : offset + 2])[0]
                    offset += 2
                    result["graphics"]["sprites"].append({"x": x, "y": y, "grh_id": graphic4})
                except struct.error as e:
                    handle_read_error(
                        "formato", f"Error al leer el gráfico adicional en ({x}, {y}): {e}", offset
                    )
                    return None

            # Leer partículas (opcional, 2 bytes)
            if by_flags & 0x20:  # Bit 5: Tiene partículas
                if offset + 2 > len(data):
                    handle_read_error(
                        "advertencia",
                        f"Archivo incompleto: Faltan 2 bytes para partículas en ({x}, {y})",
                        offset,
                    )
                    return None
                offset += 2

            # Leer luces (opcional, 2 bytes)
            if by_flags & 0x40:  # Bit 6: Tiene luces
                if offset + 2 > len(data):
                    handle_read_error(
                        "advertencia",
                        f"Archivo incompleto: Faltan 2 bytes para luces en ({x}, {y})",
                        offset,
                    )
                    return None
                offset += 2

    # Si llegamos aquí, se procesaron todas las celdas correctamente
    return result


def save_map_components(map_data: MapData, output_dir: Path, map_id: int) -> bool:
    """Guarda los datos del mapa en múltiples archivos JSON, uno por componente.

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
            "name": map_data["metadata"]["header"] or f"Mapa {map_id}",
            "width": MAP_WIDTH,
            "height": MAP_HEIGHT,
            "weather": {
                "rain": bool(map_data["metadata"]["llueve"]),
                "snow": bool(map_data["metadata"]["nieba"]),
            },
        }
        _save_json_file(output_dir / f"{map_prefix}_metadata.json", metadata)

        # 2. Guardar capa de suelo (ground)
        _save_json_file(output_dir / f"{map_prefix}_ground.json", map_data["ground"])

        # 3. Guardar capa de objetos (objects)
        _save_json_file(output_dir / f"{map_prefix}_objects.json", map_data["objects"])

        # 4. Guardar capa superior (upper)
        upper_data = [
            {"x": sprite["x"], "y": sprite["y"], "grh_id": sprite["grh_id"]}
            for sprite in map_data["upper"]["sprites"]
        ]
        _save_json_file(output_dir / f"{map_prefix}_upper.json", upper_data)

        # 5. Guardar gráficos (graphics)
        graphics_data = [
            {"x": sprite["x"], "y": sprite["y"], "grh_id": sprite["grh_id"]}
            for sprite in map_data["graphics"]["sprites"]
        ]
        _save_json_file(output_dir / f"{map_prefix}_graphics.json", graphics_data)

        # 6. Guardar flags
        _save_json_file(output_dir / f"{map_prefix}_flags.json", map_data["flags"])

        # 7. Guardar triggers
        triggers_data = [
            {
                "x": trigger["x"],
                "y": trigger["y"],
                "type": trigger["type"],
                "description": {
                    1: "Zona segura",
                    2: "Portal/Exit",
                    3: "Zona de tiendas",
                    4: "Zona de inicio",
                    5: "Mensaje al pisar",
                    6: "Trampa",
                }.get(trigger["type"], "Desconocido"),
            }
            for trigger in map_data["triggers"]
        ]
        _save_json_file(output_dir / f"{map_prefix}_triggers.json", triggers_data)

        # 8. Guardar tiles bloqueados
        blocked_tiles = []
        for y in range(MAP_HEIGHT):
            for x in range(MAP_WIDTH):
                # Definir constantes para los tipos de bloqueo
                blocked_flag = 1
                water_flag = 2

                flag = map_data["flags"][y][x]
                if flag == blocked_flag:
                    blocked_tiles.append({"x": x, "y": y, "type": "blocked"})
                elif flag == water_flag:
                    blocked_tiles.append({"x": x, "y": y, "type": "water"})
        output_file = output_dir / f"{map_prefix}_blocked.json"
        return bool(_save_json_file(output_file, blocked_tiles))

    except (OSError, json.JSONDecodeError) as e:
        print(f"Error al guardar componentes del mapa {map_id}: {e}")
        if map_data.get("metadata", {}).get("debug", False):
            traceback.print_exc()
        return False


def _save_json_file(file_path: Path, data: dict[str, Any] | list[Any]) -> bool:
    """Guarda datos en un archivo JSON con formato legible.

    Args:
        file_path: Ruta del archivo de salida
        data: Datos a guardar

    Returns:
        bool: True si se guardó correctamente, False en caso contrario
    """
    try:
        with file_path.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            return True
    except (OSError, json.JSONDecodeError) as e:
        print(f"Error al guardar {file_path}: {e}")
        return False


def get_map_id_from_filename(filename: str) -> int | None:
    """Extrae el ID numérico del mapa a partir del nombre de archivo.

    Args:
        filename: Nombre del archivo del mapa

    Returns:
        int: ID numérico del mapa o None si no se encuentra
    """
    match = re.search(r"\d+", filename)
    return int(match.group()) if match else None


def main() -> None:
    """Función principal del script.

    Analiza los argumentos de línea de comandos y convierte los mapas.
    """
    # Verificar si se proporcionó un archivo específico para depuración
    debug_file = None
    if len(sys.argv) > 1 and not sys.argv[1].startswith("-"):
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
