#!/usr/bin/env python3
"""Extraer transiciones de mapa desde los archivos .inf del servidor VB6.

Convierte las transiciones al formato transitions_XXX-XXX.json.
"""

import json
import operator
import struct
from pathlib import Path

# Constantes para rangos de mapas
MAP_RANGE_1 = 50
MAP_RANGE_2 = 100
MAP_RANGE_3 = 150
MAP_RANGE_4 = 200
MAP_RANGE_5 = 250
INT32_SIZE = 4


def read_inf_file(filepath: Path) -> list[tuple[int, int, int, int, int]]:
    """Lee un archivo .inf y extrae las transiciones de mapa.

    Args:
        filepath: Ruta al archivo .inf a leer

    Returns:
        Lista de tuplas: (x, y, to_map, to_x, to_y)
    """
    transitions = []

    try:
        with Path(filepath).open("rb") as f:
            # Saltar el header del archivo .inf
            f.seek(16)  # Header de 16 bytes

            # Leer el mapa de 100x100 tiles
            for y in range(1, 101):
                for x in range(1, 101):
                    # Leer flags byte
                    flags_byte = f.read(1)
                    if not flags_byte:
                        break

                    flags = struct.unpack("B", flags_byte)[0]

                    # Si el bit 1 está activo, hay una transición
                    if flags & 1:
                        # Leer to_map (4 bytes int32)
                        to_map_bytes = f.read(INT32_SIZE)
                        if len(to_map_bytes) < INT32_SIZE:
                            break
                        to_map = struct.unpack("<i", to_map_bytes)[0]

                        # Leer to_x (4 bytes int32)
                        to_x_bytes = f.read(INT32_SIZE)
                        if len(to_x_bytes) < INT32_SIZE:
                            break
                        to_x = struct.unpack("<i", to_x_bytes)[0]

                        # Leer to_y (4 bytes int32)
                        to_y_bytes = f.read(INT32_SIZE)
                        if len(to_y_bytes) < INT32_SIZE:
                            break
                        to_y = struct.unpack("<i", to_y_bytes)[0]

                        # Solo agregar si to_map > 0 (transición válida)
                        if to_map > 0:
                            transitions.append((x, y, to_map, to_x, to_y))

                    # Si el bit 2 está activo, hay NPC (4 bytes)
                    if flags & 2:
                        f.read(INT32_SIZE)

                    # Si el bit 4 está activo, hay objeto (8 bytes)
                    if flags & 4:
                        f.read(INT32_SIZE * 2)

                if not flags_byte:
                    break

    except (OSError, struct.error) as e:
        print(f"Error leyendo {filepath}: {e}")

    return transitions


def get_map_name(map_id: int) -> str:
    """Retorna el nombre del mapa según el ID.

    Basado en los nombres conocidos de Argentum Online.

    Args:
        map_id: ID del mapa

    Returns:
        Nombre del mapa o "Mapa {id}" si no se conoce
    """
    map_names = {
        1: "Ullathorpe",
        2: "Bosque",
        3: "Desierto",
        4: "Montañas",
        5: "Pradera",
        6: "Bosque Oscuro",
        7: "Río",
        8: "Montaña Norte",
        9: "Cañón",
        10: "Oasis",
        11: "Ruinas",
        12: "Pico Nevado",
        13: "Minas",
        14: "Costa",
        15: "Granja",
        16: "Lago",
        17: "Cementerio",
        18: "Cavernas",
        19: "Cascada",
        20: "Pantano",
        21: "Cima Helada",
        22: "Paso de Montaña",
        23: "Fortaleza",
        24: "Volcán",
        25: "Palmeral",
        26: "Dunas",
        27: "Templo Antiguo",
        28: "Laberinto",
        30: "Nix",
        31: "Lindos",
        32: "Banderbill",
        34: "Arghal",
        35: "Uthathorpe",
        36: "Veija",
        38: "Centauro",
        40: "Andarial",
        41: "Khan",
        42: "Dungeon",
        43: "Piratas",
        44: "Inferno",
        45: "Titan",
        46: "Nimrah",
        47: "Hyron",
        48: "Gladstone",
        49: "Stygian",
        50: "Buthon",
        51: "Khalos",
        52: "Khalos Dungeon",
        53: "Khalos Castle",
        54: "Khalos Underground",
        55: "Khalos Throne",
        56: "Khalos Treasury",
        57: "Khalos Library",
        58: "Khalos Laboratory",
        59: "Khalos Barracks",
        60: "Khalos Armory",
        61: "Khalos Dungeons",
        62: "Khalos Crypts",
        63: "Khalos Catacombs",
        64: "Khalos Sanctum",
        65: "Khalos Spire",
        66: "Khalos Peak",
        67: "Khalos Summit",
        68: "Khalos Apex",
        69: "Khalos Zenith",
        70: "Khalos Vertex",
        71: "Khalos Pinnacle",
        72: "Khalos Crest",
        73: "Khalos Ridge",
        74: "Khalos Summit",
        75: "Khalos Peak",
        76: "Khalos Spire",
        77: "Khalos Tower",
        78: "Khalos Keep",
        79: "Khalos Fortress",
        80: "Khalos Citadel",
        81: "Khalos Stronghold",
        82: "Khalos Bastion",
        83: "Khalos Rampart",
        84: "Khalos Bulwark",
        85: "Khalos Redoubt",
        86: "Khalos Outpost",
        87: "Khalos Garrison",
        88: "Khalos Command",
        89: "Khalos HQ",
        90: "Khalos Base",
        91: "Khalos Camp",
        92: "Khalos Station",
        93: "Khalos Post",
        94: "Khalos Fort",
        95: "Khalos Castle",
        96: "Khalos Palace",
        97: "Khalos Temple",
        98: "Khalos Shrine",
        99: "Khalos Altar",
        100: "Khalos Sanctum",
        101: "Khalos Holy",
        102: "Khalos Sacred",
        103: "Khalos Divine",
        104: "Khalos Celestial",
        105: "Khalos Ethereal",
        106: "Khalos Astral",
        107: "Khalos Cosmic",
        108: "Khalos Universal",
        109: "Khalos Infinite",
        110: "Khalos Eternal",
        111: "Khalos Immortal",
        112: "Khalos Legendary",
        113: "Khalos Mythic",
        114: "Khalos Epic",
        115: "Khalos Fabled",
        116: "Khalos Lore",
        117: "Khalos Chronicle",
        118: "Khalos Saga",
        119: "Khalos Tale",
        120: "Khalos Story",
    }

    return map_names.get(map_id, f"Mapa {map_id}")


def create_transitions_file(
    map_id: int, transitions: list[tuple[int, int, int, int, int]], output_dir: Path
) -> None:
    """Crea un archivo transitions_XXX-XXX.json con las transiciones del mapa.

    Args:
        map_id: ID del mapa
        transitions: Lista de tuplas (x, y, to_map, to_x, to_y)
        output_dir: Directorio donde guardar el archivo
    """
    if not transitions:
        return

    # Determinar el rango del archivo
    if map_id <= MAP_RANGE_1:
        range_str = "001-050"
    elif map_id <= MAP_RANGE_2:
        range_str = "051-100"
    elif map_id <= MAP_RANGE_3:
        range_str = "101-150"
    elif map_id <= MAP_RANGE_4:
        range_str = "151-200"
    elif map_id <= MAP_RANGE_5:
        range_str = "201-250"
    else:
        range_str = "251-290"

    filename = f"transitions_{range_str}.json"
    filepath = output_dir / filename

    # Crear estructura de transiciones
    exits = []
    for x, y, to_map, to_x, to_y in transitions:
        exits.append(
            {
                "x": x,
                "y": y,
                "to_map": to_map,
                "to_x": to_x,
                "to_y": to_y,
                "description": (
                    f"Salida desde {get_map_name(map_id)} ({x},{y}) -> "
                    f"{get_map_name(to_map)} ({to_x},{to_y})"
                ),
            }
        )

    transition_data = {"from_map": map_id, "from_name": get_map_name(map_id), "exits": exits}

    # Leer archivo existente si existe
    existing_data = {"transitions": []}
    if filepath.exists():
        try:
            with Path(filepath).open(encoding="utf-8") as f:
                existing_data = json.load(f)
        except (OSError, json.JSONDecodeError):
            # Si el archivo está corrupto, usar estructura vacía
            pass

    # Buscar si ya existe transición para este mapa
    found = False
    for i, trans in enumerate(existing_data["transitions"]):
        if trans["from_map"] == map_id:
            existing_data["transitions"][i] = transition_data
            found = True
            break

    if not found:
        existing_data["transitions"].append(transition_data)

    # Ordenar transiciones por from_map
    existing_data["transitions"].sort(key=operator.itemgetter("from_map"))

    # Guardar archivo
    with Path(filepath).open("w", encoding="utf-8") as f:
        json.dump(existing_data, f, indent=2, ensure_ascii=False)

    print(
        f"✅ Mapa {map_id} ({get_map_name(map_id)}): {len(transitions)} transiciones -> {filename}"
    )


def main() -> None:
    """Función principal para extraer todas las transiciones.

    Extrae transiciones de archivos .inf del servidor VB6 y las guarda
    en archivos JSON organizados por rangos.
    """
    # Directorios
    vb6_maps_dir = Path("clientes/ArgentumOnline0.13.3-Cliente-Servidor/server/Maps")
    output_dir = Path("map_data")

    if not vb6_maps_dir.exists():
        print(f"❌ No existe el directorio: {vb6_maps_dir}")
        return

    # Crear directorio de salida si no existe
    output_dir.mkdir(exist_ok=True)

    print("🔍 Extrayendo transiciones desde archivos .inf del servidor VB6...")

    # Buscar todos los archivos .inf
    inf_files = list(vb6_maps_dir.glob("Mapa*.inf"))
    print(f"📁 Encontrados {len(inf_files)} archivos .inf")

    total_transitions = 0
    maps_with_transitions = 0

    for inf_file in sorted(inf_files):
        # Extraer ID del mapa del nombre del archivo
        try:
            map_id = int(inf_file.stem.replace("Mapa", ""))
        except ValueError:
            # Si el nombre del archivo no tiene formato válido, saltar
            continue

        # Extraer transiciones
        transitions = read_inf_file(inf_file)

        if transitions:
            create_transitions_file(map_id, transitions, output_dir)
            total_transitions += len(transitions)
            maps_with_transitions += 1
        else:
            print(f"⚪ Mapa {map_id}: Sin transiciones")

    print("\n📊 Resumen:")
    print(f"   - Mapas procesados: {len(inf_files)}")
    print(f"   - Mapas con transiciones: {maps_with_transitions}")
    print(f"   - Total de transiciones: {total_transitions}")
    print(f"\n✅ Proceso completado. Archivos guardados en {output_dir}")


if __name__ == "__main__":
    main()
