"""Script para extraer tiles bloqueados de archivos .map de Argentum Online.

Este script lee los archivos .map del cliente Godot y extrae información sobre
qué tiles están bloqueados en cada mapa.

Formato del archivo .map de AO:
- Archivo binario con información de cada tile (100x100 tiles)
- Cada tile tiene información sobre si es bloqueado o no
"""

from pathlib import Path


def read_map_file(map_path: Path) -> dict[tuple[int, int], bool]:
    """Lee un archivo .map y extrae los tiles bloqueados.

    Args:
        map_path: Ruta al archivo .map

    Returns:
        Diccionario con (x, y) -> is_blocked
    """
    blocked_tiles = {}

    try:
        with map_path.open("rb") as f:
            data = f.read()

        # El formato .map de AO tiene información por tile
        # Cada tile ocupa varios bytes con información de gráficos y flags
        # El flag de bloqueo suele estar en un byte específico

        # Formato aproximado (puede variar según versión):
        # Por cada tile (x, y):
        #   - Gráficos de capas (varios int16)
        #   - Flags de bloqueo (byte)
        #   - Otros datos

        # Tamaño típico por tile: ~30 bytes
        bytes_per_tile = len(data) // (100 * 100)

        print(f"Archivo: {map_path.name}")
        print(f"  Tamaño: {len(data)} bytes")
        print(f"  Bytes por tile: {bytes_per_tile}")

        # Intentar parsear tiles bloqueados
        # Nota: El formato exacto puede variar, esto es una aproximación
        offset = 0
        for y in range(1, 101):
            for x in range(1, 101):
                if offset + bytes_per_tile > len(data):
                    break

                tile_data = data[offset : offset + bytes_per_tile]

                # El byte de bloqueo suele estar cerca del final del tile
                # Típicamente en posición -4 o -3
                if len(tile_data) >= 4:
                    blocked_byte = tile_data[-4]
                    is_blocked = (blocked_byte & 0x01) != 0  # Bit 0 = bloqueado

                    if is_blocked:
                        blocked_tiles[x, y] = True

                offset += bytes_per_tile

        print(f"  Tiles bloqueados: {len(blocked_tiles)}")

    except Exception as e:
        print(f"Error leyendo {map_path.name}: {e}")

    return blocked_tiles


def extract_all_maps(
    maps_dir: str = "./clientes/ArgentumOnlineGodot/Assets/Maps",
) -> dict[int, dict[tuple[int, int], bool]]:
    """Extrae tiles bloqueados de todos los mapas.

    Args:
        maps_dir: Directorio con archivos .map

    Returns:
        Diccionario con map_id -> {(x, y) -> is_blocked}
    """
    maps_path = Path(maps_dir)
    all_blocked_tiles = {}

    if not maps_path.exists():
        print(f"Directorio no encontrado: {maps_dir}")
        return all_blocked_tiles

    # Obtener todos los archivos .map
    map_files = sorted(maps_path.glob("mapa*.map"))

    print(f"Encontrados {len(map_files)} archivos .map\n")

    for map_file in map_files:
        # Extraer número de mapa del nombre (mapa1.map -> 1)
        try:
            map_id = int(map_file.stem.replace("mapa", ""))
        except ValueError:
            continue

        blocked_tiles = read_map_file(map_file)
        all_blocked_tiles[map_id] = blocked_tiles
        print()

    return all_blocked_tiles


def generate_toml_config(
    all_blocked_tiles: dict[int, dict[tuple[int, int], bool]],
    output_file: str = "data/map_blocked_tiles.toml",
) -> None:
    """Genera archivo TOML con tiles bloqueados.

    Args:
        all_blocked_tiles: Diccionario con tiles bloqueados por mapa
        output_file: Ruta del archivo de salida
    """
    output_path = Path(output_file)

    with output_path.open("w", encoding="utf-8") as f:
        f.write("# Tiles bloqueados por mapa\n")
        f.write("# Generado automáticamente desde archivos .map del cliente\n")
        f.write("# Formato: [[map]] id = X, blocked_tiles = [[x, y], [x, y], ...]\n\n")

        for map_id in sorted(all_blocked_tiles.keys()):
            blocked_tiles = all_blocked_tiles[map_id]

            if not blocked_tiles:
                continue

            f.write("[[map]]\n")
            f.write(f"id = {map_id}\n")
            f.write("blocked_tiles = [\n")

            # Escribir tiles bloqueados en grupos de 10 por línea
            tiles_list = sorted(blocked_tiles.keys())
            for i in range(0, len(tiles_list), 10):
                chunk = tiles_list[i : i + 10]
                tiles_str = ", ".join([f"[{x}, {y}]" for x, y in chunk])
                f.write(f"    {tiles_str},\n")

            f.write("]\n\n")

    print(f"\n✅ Archivo generado: {output_file}")
    print(f"   Total mapas: {len(all_blocked_tiles)}")
    total_blocked = sum(len(tiles) for tiles in all_blocked_tiles.values())
    print(f"   Total tiles bloqueados: {total_blocked}")


if __name__ == "__main__":
    print("=" * 60)
    print("Extractor de Tiles Bloqueados - Argentum Online")
    print("=" * 60)
    print()

    # Extraer tiles bloqueados
    all_blocked_tiles = extract_all_maps()

    # Generar archivo TOML
    if all_blocked_tiles:
        generate_toml_config(all_blocked_tiles)
    else:
        print("\n⚠️  No se encontraron mapas para procesar")
