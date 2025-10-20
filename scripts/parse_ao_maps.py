"""Parser de archivos .map de Argentum Online.

Basado en el código del cliente Godot en game_assets.gd
"""

import struct
from pathlib import Path


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
    if layer2 == 0:
        if (1505 <= layer1 <= 1520) or (5665 <= layer1 <= 5680) or (13547 <= layer1 <= 13562):
            return "water"

    # Edificios y paredes (rango 6000-6200 muy común en mapas)
    if 6000 <= layer1 <= 6200:
        return "building"

    # Árboles (rangos comunes)
    if (6076 <= layer1 <= 6120) or (5500 <= layer1 <= 5600) or (8600 <= layer1 <= 8700):
        return "tree"

    # Rocas y montañas
    if (6200 <= layer1 <= 6400) or (5700 <= layer1 <= 5800):
        return "rock"

    # Muros y vallas
    if (5400 <= layer1 <= 5500) or (8500 <= layer1 <= 8600):
        return "wall"

    # Por defecto, bloqueado genérico
    return "blocked"


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
    tile_types_count = {}

    with map_path.open("rb") as f:
        # Saltar header (273 bytes)
        f.seek(2 + 255 + 4 + 4 + 8)

        # Leer 100x100 tiles
        for y in range(100):
            for x in range(100):
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

                # Layer 2 (si flags & 0x2)
                layer2 = 0
                if flags & 0x2:
                    layer2_bytes = f.read(2)
                    if layer2_bytes:
                        layer2 = struct.unpack("<H", layer2_bytes)[0]

                # Layer 3 (si flags & 0x4)
                if flags & 0x4:
                    f.read(2)  # Saltar layer3

                # Layer 4 (si flags & 0x8)
                if flags & 0x8:
                    f.read(2)  # Saltar layer4

                # Trigger (si flags & 0x10)
                if flags & 0x10:
                    f.read(2)  # Saltar trigger

                # Verificar si está bloqueado (bit 0x1)
                if flags & 0x1:
                    tile_type = detect_tile_type(layer1, layer2)
                    blocked_tiles.append({"x": x + 1, "y": y + 1, "type": tile_type})
                    tile_types_count[tile_type] = tile_types_count.get(tile_type, 0) + 1

    return {"blocked_tiles": blocked_tiles, "tile_types_count": tile_types_count}


def extract_map_data(
    map_id: int, maps_dir: str = "./clientes/ArgentumOnlineGodot/Assets/Maps"
) -> dict | None:
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


def generate_map_json(map_id: int, name: str, map_data: dict) -> dict:
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
