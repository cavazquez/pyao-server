"""Parser de archivos .map de Argentum Online.

Basado en el código del cliente Godot en game_assets.gd
"""

import struct
from pathlib import Path
from typing import Any

# Rangos de GRH para detección de tipos de tiles
WATER_RANGE_1 = (1505, 1520)
WATER_RANGE_2 = (5665, 5680)
WATER_RANGE_3 = (13547, 13562)
BUILDING_RANGE = (6000, 6200)
TREE_RANGE_1 = (6076, 6120)
TREE_RANGE_2 = (5500, 5600)
TREE_RANGE_3 = (8600, 8700)
ROCK_RANGE_1 = (6200, 6400)
ROCK_RANGE_2 = (5700, 5800)
WALL_RANGE_1 = (5400, 5500)
WALL_RANGE_2 = (8500, 8600)
HEADER_SIZE = 273
MAP_SIZE = 100
LAYER_FLAGS = {
    "layer2": 0x2,
    "layer3": 0x4,
    "layer4": 0x8,
    "trigger": 0x10,
}
BLOCKED_FLAG = 0x1


def detect_tile_type(layer1: int, layer2: int) -> str:
    """Detecta el tipo de tile bloqueado según el gráfico.

    Basado en análisis de GRH reales de los mapas de AO.

    Args:
        layer1: Gráfico de capa 1
        layer2: Gráfico de capa 2

    Returns:
        Tipo de tile: "tree", "rock", "wall", "building", "water", "blocked"
    """
    # Agua (debe tener layer2 == 0)
    if layer2 == 0 and (
        (WATER_RANGE_1[0] <= layer1 <= WATER_RANGE_1[1])
        or (WATER_RANGE_2[0] <= layer1 <= WATER_RANGE_2[1])
        or (WATER_RANGE_3[0] <= layer1 <= WATER_RANGE_3[1])
    ):
        return "water"

    # Edificios y paredes
    if BUILDING_RANGE[0] <= layer1 <= BUILDING_RANGE[1]:
        return "building"

    # Árboles
    if (
        (TREE_RANGE_1[0] <= layer1 <= TREE_RANGE_1[1])
        or (TREE_RANGE_2[0] <= layer1 <= TREE_RANGE_2[1])
        or (TREE_RANGE_3[0] <= layer1 <= TREE_RANGE_3[1])
    ):
        return "tree"

    # Rocas y montañas
    if (ROCK_RANGE_1[0] <= layer1 <= ROCK_RANGE_1[1]) or (
        ROCK_RANGE_2[0] <= layer1 <= ROCK_RANGE_2[1]
    ):
        return "rock"

    # Muros y vallas
    if (WALL_RANGE_1[0] <= layer1 <= WALL_RANGE_1[1]) or (
        WALL_RANGE_2[0] <= layer1 <= WALL_RANGE_2[1]
    ):
        return "wall"

    # Por defecto, bloqueado genérico
    return "blocked"


def parse_map_file(map_path: Path) -> dict[str, Any]:
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
    blocked_tiles: list[dict[str, Any]] = []
    tile_types_count: dict[str, int] = {}

    with map_path.open("rb") as f:
        # Saltar header
        f.seek(HEADER_SIZE)

        # Leer tiles del mapa
        for y in range(MAP_SIZE):
            for x in range(MAP_SIZE):
                # Leer flags
                flags_byte = f.read(1)
                if not flags_byte:
                    break
                flags = struct.unpack("B", flags_byte)[0]

                # Layer 1 (siempre presente)
                layer1_bytes = f.read(2)
                if not layer1_bytes:
                    break
                layer1 = struct.unpack("<H", layer1_bytes)[0]

                # Layer 2
                layer2 = 0
                if flags & LAYER_FLAGS["layer2"]:
                    layer2_bytes = f.read(2)
                    if layer2_bytes:
                        layer2 = struct.unpack("<H", layer2_bytes)[0]

                # Layer 3
                if flags & LAYER_FLAGS["layer3"]:
                    f.read(2)  # Saltar layer3

                # Layer 4
                if flags & LAYER_FLAGS["layer4"]:
                    f.read(2)  # Saltar layer4

                # Trigger
                if flags & LAYER_FLAGS["trigger"]:
                    f.read(2)  # Saltar trigger

                # Verificar si está bloqueado
                if flags & BLOCKED_FLAG:
                    tile_type = detect_tile_type(layer1, layer2)
                    blocked_tiles.append({"x": x + 1, "y": y + 1, "type": tile_type})
                    tile_types_count[tile_type] = tile_types_count.get(tile_type, 0) + 1

    return {"blocked_tiles": blocked_tiles, "tile_types_count": tile_types_count}


def extract_map_data(
    map_id: int, maps_dir: str = "./clientes/ArgentumOnlineGodot/Assets/Maps"
) -> dict[str, Any] | None:
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

    total_blocked = len(data["blocked_tiles"])
    print(f"   ✅ {total_blocked} tiles bloqueados:")

    # Mostrar desglose por tipo
    for tile_type, count in sorted(data["tile_types_count"].items()):
        percentage = (count / total_blocked * 100) if total_blocked > 0 else 0
        print(f"      - {tile_type}: {count} ({percentage:.1f}%)")

    return data


def generate_map_json(map_id: int, name: str, map_data: dict[str, Any]) -> dict[str, Any]:
    """Genera estructura JSON para un mapa.

    Args:
        map_id: ID del mapa
        name: Nombre del mapa
        map_data: Datos extraídos del .map

    Returns:
        Diccionario con estructura del mapa
    """
    return {
        "id": map_id,
        "name": name,
        "width": 100,
        "height": 100,
        "blocked_tiles": map_data["blocked_tiles"],
        "spawn_points": [{"x": 50, "y": 50, "description": f"Centro de {name}"}],
    }


def update_all_maps() -> None:
    """Actualiza archivos JSON de todos los mapas disponibles."""
    maps_dir = Path("maps")
    maps_dir.mkdir(exist_ok=True)

    # Buscar todos los archivos .map disponibles
    client_maps_dir = Path("./clientes/ArgentumOnlineGodot/Assets/Maps")
    map_files = sorted(client_maps_dir.glob("mapa*.map"))

    # Extraer IDs de los mapas
    maps_config = []
    for map_file in map_files:
        try:
            map_id = int(map_file.stem.replace("mapa", ""))
            maps_config.append((map_id, f"Mapa {map_id}"))
        except ValueError:
            continue

    print("=" * 70)
    print("Parser de Mapas de Argentum Online")
    print("=" * 70)
    print()

    for map_id, name in maps_config:
        # Extraer datos del .map
        map_data = extract_map_data(map_id)

        if not map_data:
            print(f"   ⚠️  Usando datos vacíos para mapa {map_id}\n")
            map_data = {"blocked_tiles": [], "tile_types_count": {}}

        # Generar JSON
        map_json = generate_map_json(map_id, name, map_data)

        # Guardar archivo con formato compacto para blocked_tiles
        output_file = maps_dir / f"map_{map_id}.json"
        with output_file.open("w", encoding="utf-8") as f:
            # Escribir manualmente para formato horizontal
            f.write("{\n")
            f.write(f'  "id": {map_json["id"]},\n')
            f.write(f'  "name": "{map_json["name"]}",\n')
            f.write(f'  "width": {map_json["width"]},\n')
            f.write(f'  "height": {map_json["height"]},\n')
            f.write('  "blocked_tiles": [\n')

            # Escribir tiles en formato horizontal (un tile por línea)
            for i, tile in enumerate(map_json["blocked_tiles"]):
                comma = "," if i < len(map_json["blocked_tiles"]) - 1 else ""
                f.write(
                    f'    {{"x": {tile["x"]}, "y": {tile["y"]}, "type": "{tile["type"]}"}}{comma}\n'
                )

            f.write("  ],\n")
            f.write('  "spawn_points": [\n')

            for i, spawn in enumerate(map_json["spawn_points"]):
                comma = "," if i < len(map_json["spawn_points"]) - 1 else ""
                spawn_line = (
                    f'    {{"x": {spawn["x"]}, "y": {spawn["y"]}, '
                    f'"description": "{spawn["description"]}"}}{comma}\n'
                )
                f.write(spawn_line)

            f.write("  ]\n")
            f.write("}\n")

        total_blocked = len(map_json["blocked_tiles"])
        print(f"   💾 Guardado: {output_file} ({total_blocked} tiles bloqueados)")
        print()

    print("=" * 70)
    print(f"✅ {len(maps_config)} mapas actualizados correctamente")
    print("=" * 70)


if __name__ == "__main__":
    update_all_maps()
