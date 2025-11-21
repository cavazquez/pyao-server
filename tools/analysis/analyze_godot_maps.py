#!/usr/bin/env python3
"""Analizar archivos .map del cliente Godot para extraer transiciones."""

import struct
from pathlib import Path

# Constantes
FLAGS_SIZE = 3
MAX_TRIGGER_ID = 1000


def analyze_map_file(filepath: Path) -> list[tuple[int, int, int, int, int]]:
    """Analiza un archivo .map del cliente Godot y extrae transiciones.

    Args:
        filepath: Ruta al archivo .map a analizar

    Returns:
        Lista de tuplas con transiciones encontradas (x, y, to_map, to_x, to_y)
    """
    transitions = []

    try:
        with Path(filepath).open("rb") as f:
            # Leer header del archivo .map
            # Los archivos .map de AO tienen un formato específico

            # Saltar headers (generalmente 272 bytes para headers de mapa)
            f.seek(272)

            # Leer el mapa de 100x100 tiles
            for _y in range(1, 101):
                for _x in range(1, 101):
                    # Cada tile tiene varios layers y flags
                    # Leer flags (3 bytes)
                    flags_data = f.read(FLAGS_SIZE)
                    if len(flags_data) < FLAGS_SIZE:
                        break

                    # Leer 4 layers de gráficos (4 bytes cada uno)
                    struct.unpack("<i", f.read(4))[0]
                    struct.unpack("<i", f.read(4))[0]
                    struct.unpack("<i", f.read(4))[0]
                    struct.unpack("<i", f.read(4))[0]

                    # Leer trigger (4 bytes)
                    trigger = struct.unpack("<i", f.read(4))[0]

                    # Revisar si hay trigger de teleport
                    if 0 < trigger < MAX_TRIGGER_ID:  # IDs de trigger válidos
                        # Los triggers pueden contener datos de teletransporte
                        # Necesitamos buscar en la tabla de triggers
                        pass

                if len(flags_data) < FLAGS_SIZE:
                    break

    except (OSError, struct.error) as e:
        print(f"Error analizando {filepath}: {e}")

    return transitions


def main() -> None:
    """Función principal.

    Analiza archivos .map del cliente Godot para buscar transiciones.
    """
    godot_maps_dir = Path("clientes/ArgentumOnlineGodot/Assets/Maps")

    if not godot_maps_dir.exists():
        print(f"❌ No existe el directorio: {godot_maps_dir}")
        return

    # Buscar archivos .map
    map_files = list(godot_maps_dir.glob("*.map"))
    print(f"📁 Encontrados {len(map_files)} archivos .map en el cliente Godot")

    # Analizar primeros 10 mapas
    for map_file in sorted(map_files)[:10]:
        map_id = int(map_file.stem.replace("mapa", ""))
        transitions = analyze_map_file(map_file)
        print(f"Mapa {map_id}: {len(transitions)} transiciones potenciales")


if __name__ == "__main__":
    main()
