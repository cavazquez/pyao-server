#!/usr/bin/env python3
"""Extrae los tamaños reales de los archivos .map del cliente."""

import struct
from pathlib import Path


def read_map_size(map_file: Path) -> tuple[int, int, int]:
    """Lee el tamaño de un archivo .map.

    Formato del archivo .map (primeros bytes):
    - 2 bytes: version (int16)
    - 2 bytes: width (int16)
    - 2 bytes: height (int16)

    Returns:
        Tupla (map_id, width, height)
    """
    try:
        with Path(map_file).open("rb") as f:
            # Leer primeros 6 bytes
            data = f.read(6)
            if len(data) < 6:
                return (0, 0, 0)

            # Desempaquetar: version, width, height (little-endian int16)
            version, width, height = struct.unpack("<HHH", data)

            # Extraer ID del mapa desde el nombre del archivo
            # mapa1.map -> 1, mapa123.map -> 123
            map_name = map_file.stem  # 'mapa1'
            map_id = int(map_name.replace("mapa", ""))

            return (map_id, width, height)
    except Exception as e:
        print(f"Error leyendo {map_file}: {e}")
        return (0, 0, 0)


def main():
    """Extrae tamaños de todos los mapas."""
    maps_dir = Path("clientes/ArgentumOnlineGodot/Assets/Maps")

    if not maps_dir.exists():
        print(f"❌ Directorio no encontrado: {maps_dir}")
        return

    # Leer todos los archivos .map
    map_files = sorted(maps_dir.glob("mapa*.map"))

    print(f"📁 Encontrados {len(map_files)} archivos .map")
    print("\n" + "=" * 60)
    print(f"{'Map ID':<10} {'Width':<10} {'Height':<10}")
    print("=" * 60)

    sizes = {}
    for map_file in map_files:
        map_id, width, height = read_map_size(map_file)
        if map_id > 0:
            sizes[map_id] = (width, height)
            print(f"{map_id:<10} {width:<10} {height:<10}")

    # Mostrar resumen
    print("\n" + "=" * 60)
    print("📊 RESUMEN:")
    print("=" * 60)

    # Agrupar por tamaño
    size_counts = {}
    for width, height in sizes.values():
        size_key = f"{width}x{height}"
        size_counts[size_key] = size_counts.get(size_key, 0) + 1

    for size, count in sorted(size_counts.items()):
        print(f"{size}: {count} mapas")

    # Encontrar mapas con tamaños no estándar
    print("\n" + "=" * 60)
    print("🔍 MAPAS NO ESTÁNDAR (no 100x100):")
    print("=" * 60)

    non_standard = []
    for map_id, (width, height) in sorted(sizes.items()):
        if width != 100 or height != 100:
            non_standard.append((map_id, width, height))
            print(f"Mapa {map_id}: {width}x{height}")

    if not non_standard:
        print("✅ Todos los mapas son 100x100")

    print(f"\n✅ Total: {len(sizes)} mapas procesados")


if __name__ == "__main__":
    main()
