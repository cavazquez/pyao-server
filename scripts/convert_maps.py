#!/usr/bin/env python3
"""Convertidor de mapas binarios de Argentum Online a JSON.

Este script convierte los archivos `.map` de los clientes VB6 y Godot de Argentum Online
en archivos JSON por capa usando el patrón `XXX_*.json`, guardados directamente en el
directorio ``map_data``.
"""

import json
import re
import struct
import sys
import traceback
from pathlib import Path
from typing import Any, TextIO, TypedDict

import tomllib

# Configuración de fuentes de mapas
VB6_MAPS_SOURCE_DIR = Path("clientes/ArgentumOnline0.13.3-Cliente-Servidor/client/Mapas")
GODOT_MAPS_SOURCE_DIR = Path("clientes/ArgentumOnlineGodot/Assets/Maps")
MAPS_OUTPUT_DIR = Path("map_data")
MAP_TRANSITIONS_FILE = Path("data/map_transitions.toml")

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
    truncated_warnings: list[str] = []

    def read_bytes(num_bytes: int, description: str) -> bytes:
        """Lee bytes del buffer y rellena con ceros si faltan datos."""

        nonlocal offset
        end = offset + num_bytes
        if end <= len(data):
            chunk = data[offset:end]
        else:
            available = max(0, len(data) - offset)
            chunk = data[offset: len(data)] if offset < len(data) else b""
            missing = num_bytes - available
            chunk += b"\x00" * missing
            truncated_warnings.append(
                f"{description} (faltaban {missing} bytes en offset {offset})"
            )
        offset = end
        return chunk

    # Leer versión del mapa (2 bytes, little-endian)
    version_bytes = read_bytes(2, "versión del mapa")
    result["metadata"]["version"] = struct.unpack("<H", version_bytes)[0]

    # Leer cabecera (100 bytes, string terminado en null)
    header_bytes = read_bytes(100, "cabecera del mapa")
    header = header_bytes.split(b"\x00")[0].decode("latin-1", errors="ignore")
    result["metadata"]["header"] = header.strip()

    # Leer clima (llueve, nieba)
    weather_mapping = ["llueve", "nieba"]
    for weather_type in weather_mapping:
        value_bytes = read_bytes(2, f"valor de clima {weather_type}")
        value = struct.unpack("<H", value_bytes)[0]
        result["metadata"][weather_type] = value

    # Saltar campos temporales (4 * 2 bytes = 8 bytes)
    read_bytes(8, "campos temporales reservados")

    # Procesar cada celda del mapa (100x100)
    for y in range(MAP_HEIGHT):
        for x in range(MAP_WIDTH):
            # Leer flags del tile (1 byte)
            by_flags = read_bytes(1, f"flags en ({x}, {y})")[0]

            # Leer gráfico de la capa base (siempre presente, 2 bytes)
            ground_bytes = read_bytes(2, f"capa base en ({x}, {y})")
            graphic1 = struct.unpack("<H", ground_bytes)[0]
            result["ground"][y][x] = graphic1

            # Marcar como bloqueado si corresponde
            if by_flags & 0x01:  # Bit 0: Bloqueado
                result["flags"][y][x] = 1

            # Leer capa de objetos (opcional, 2 bytes)
            if by_flags & 0x02:  # Bit 1: Tiene objeto
                object_bytes = read_bytes(2, f"objeto en ({x}, {y})")
                result["objects"][y][x] = struct.unpack("<H", object_bytes)[0]

            # Leer capa superior (opcional, 2 bytes)
            if by_flags & 0x04:  # Bit 2: Tiene capa superior
                upper_bytes = read_bytes(2, f"capa superior en ({x}, {y})")
                result["upper"]["sprites"].append(
                    {"x": x, "y": y, "grh_id": struct.unpack("<H", upper_bytes)[0]}
                )

            # Leer triggers (opcional, 1 byte)
            if by_flags & 0x08:  # Bit 3: Tiene trigger
                trigger_type = read_bytes(1, f"trigger en ({x}, {y})")[0]
                result["triggers"].append({"x": x, "y": y, "type": trigger_type})

            # Leer gráficos adicionales (opcional, 2 bytes)
            if by_flags & 0x10:  # Bit 4: Tiene gráfico adicional
                extra_bytes = read_bytes(2, f"gráfico adicional en ({x}, {y})")
                result["graphics"]["sprites"].append(
                    {"x": x, "y": y, "grh_id": struct.unpack("<H", extra_bytes)[0]}
                )

            # Leer partículas (opcional, 2 bytes)
            if by_flags & 0x20:  # Bit 5: Tiene partículas
                read_bytes(2, f"partículas en ({x}, {y})")

            # Leer luces (opcional, 2 bytes)
            if by_flags & 0x40:  # Bit 6: Tiene luces
                read_bytes(2, f"luces en ({x}, {y})")

    if truncated_warnings:
        print(
            f"  ⚠️  Archivo incompleto: {map_path.name} se rellenó con ceros en "
            f"{len(truncated_warnings)} lecturas"
        )
        if debug:
            for warning in truncated_warnings:
                print(f"     - {warning}")

    return result


def _load_map_transitions(path: Path) -> dict[tuple[int, str], dict[str, int]]:
    """Carga las transiciones de mapas desde un archivo TOML."""
    if not path.exists():
        return {}

    try:
        with path.open("rb") as f:
            data = tomllib.load(f)
    except tomllib.TOMLDecodeError as exc:
        print(f"  ✗ Error al leer transiciones desde {path}: {exc}")
        return {}

    transitions: dict[tuple[int, str], dict[str, int]] = {}
    for entry in data.get("transition", []):
        try:
            from_map = int(entry["from_map"])
            edge = str(entry["edge"])
            transitions[(from_map, edge)] = {
                "to_map": int(entry["to_map"]),
                "to_x": int(entry["to_x"]),
                "to_y": int(entry["to_y"]),
            }
        except (KeyError, ValueError, TypeError) as exc:
            print(f"  ✗ Entrada de transición inválida {entry}: {exc}")
    return transitions


TRANSITIONS = _load_map_transitions(MAP_TRANSITIONS_FILE)


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

        # 3. (Intencionalmente omitido) capa de objetos
        # El cliente Godot gestiona esta capa desde los archivos originales.

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
        blocked_tiles: list[dict[str, int | str]] = []
        edge_threshold = 4
        transitions_for_map = {edge: data for (mid, edge), data in TRANSITIONS.items() if mid == map_id}

        def _maybe_add_exit_tile(x: int, y: int) -> dict[str, int | str] | None:
            if not transitions_for_map:
                return None

            edge: str | None = None
            if y < edge_threshold:
                edge = "north"
            elif y >= MAP_HEIGHT - edge_threshold:
                edge = "south"
            elif x < edge_threshold:
                edge = "west"
            elif x >= MAP_WIDTH - edge_threshold:
                edge = "east"

            if edge is None:
                return None

            transition = transitions_for_map.get(edge)
            if not transition:
                return None

            return {
                "x": x,
                "y": y,
                "type": "exit",
                "to_map": transition["to_map"],
                "to_x": transition["to_x"],
                "to_y": transition["to_y"],
            }

        for y in range(MAP_HEIGHT):
            for x in range(MAP_WIDTH):
                flag = map_data["flags"][y][x]
                ground_tile = map_data["ground"][y][x]

                if flag == 1:
                    exit_tile = _maybe_add_exit_tile(x, y)
                    if exit_tile:
                        blocked_tiles.append(exit_tile)
                    else:
                        blocked_tiles.append({"x": x, "y": y, "type": "blocked"})
                elif is_water(ground_tile):
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
            if _write_matrix_rows(f, data) or _write_object_rows(f, data):
                return True
            json.dump(data, f, indent=2, ensure_ascii=False)
            return True
    except (OSError, json.JSONDecodeError) as e:
        print(f"Error al guardar {file_path}: {e}")
        return False


def _write_matrix_rows(file_handle: TextIO, data: Any) -> bool:
    """Escribe matrices numéricas con una fila por línea."""
    if (
        not isinstance(data, list)
        or not data
        or not all(isinstance(row, list) for row in data)
        or not all(all(isinstance(value, int) for value in row) for row in data)
    ):
        return False

    file_handle.write("[\n")
    last_index = len(data) - 1
    for index, row in enumerate(data):
        row_json = json.dumps(row, ensure_ascii=False)
        file_handle.write(f"  {row_json}")
        if index != last_index:
            file_handle.write(",")
        file_handle.write("\n")
    file_handle.write("]\n")
    return True


def _write_object_rows(file_handle: TextIO, data: Any) -> bool:
    """Escribe listas de diccionarios con un objeto por línea."""
    if not isinstance(data, list) or not data or not all(isinstance(item, dict) for item in data):
        return False

    file_handle.write("[\n")
    last_index = len(data) - 1
    for index, item in enumerate(data):
        item_json = json.dumps(item, ensure_ascii=False, separators=(", ", ": "))
        file_handle.write(f"  {item_json}")
        if index != last_index:
            file_handle.write(",")
        file_handle.write("\n")
    file_handle.write("]\n")
    return True


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
        debug_file = Path(sys.argv[1])
        print(f"Modo depuración: Procesando solo {debug_file}")
        map_candidates: list[tuple[int, Path, str]] = []
        map_id = get_map_id_from_filename(debug_file.name)
        if map_id is not None:
            map_candidates.append((map_id, debug_file, "custom"))
        else:
            print(f"  ✗ No se pudo obtener el ID del mapa: {debug_file}")
            return
    else:
        map_candidates = []
        sources = [
            ("VB6", VB6_MAPS_SOURCE_DIR),
            ("Godot", GODOT_MAPS_SOURCE_DIR),
        ]

        for source_name, source_dir in sources:
            if not source_dir.exists():
                print(f"⚠️  Directorio no encontrado ({source_name}): {source_dir}")
                continue

            for map_path in source_dir.glob("*.map"):
                map_id = get_map_id_from_filename(map_path.name)
                if map_id is None:
                    print(f"  ✗ No se pudo obtener el ID del mapa: {map_path.name}")
                    continue
                map_candidates.append((map_id, map_path, source_name))

        # Priorizar mapas VB6 frente a Godot si hay duplicados
        deduped: dict[int, tuple[Path, str]] = {}
        for map_id, map_path, source_name in sorted(map_candidates, key=lambda item: item[0]):
            if map_id in deduped:
                # Preferir VB6 si existe, dejar aviso para otros duplicados
                if deduped[map_id][1] == "VB6":
                    print(
                        f"  ⚠️  Mapa {map_id:03d} duplicado en {source_name}, se mantiene versión VB6"
                    )
                    continue
                if source_name == "VB6":
                    print(
                        f"  ⚠️  Mapa {map_id:03d} existe en Godot, pero se reemplazará por versión VB6"
                    )
                deduped[map_id] = (map_path, source_name)
            else:
                deduped[map_id] = (map_path, source_name)

        map_candidates = [
            (map_id, path, source) for map_id, (path, source) in sorted(deduped.items())
        ]

    total_maps = len(map_candidates)
    success_count = 0

    print(f"Iniciando conversión de {total_maps} mapas...")

    for map_id, map_path, source_name in map_candidates:
        print(f"Procesando {map_path.name} (ID: {map_id}, fuente: {source_name})...")

        # Parsear el archivo .map
        map_data = parse_map_file(map_path, debug=debug_file is not None)
        if map_data is None:
            print("  ✗ Error al parsear el archivo")
            continue

        # Guardar los componentes del mapa en archivos separados
        if save_map_components(map_data, MAPS_OUTPUT_DIR, map_id):
            success_count += 1
            print(
                f"  ✓ Convertido a JSON en {MAPS_OUTPUT_DIR}/ como {map_id:03d}_*.json"
            )
        else:
            print(
                f"  ✗ Error al guardar los archivos JSON en {MAPS_OUTPUT_DIR}/"
            )

    print(
        f"\nConversión completada: {success_count}/{total_maps} mapas convertidos exitosamente"
    )
    if success_count < total_maps:
        print(f"  - {total_maps - success_count} mapas con errores")


if __name__ == "__main__":
    main()
