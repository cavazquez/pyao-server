#!/usr/bin/env python3
"""
Script para extraer todos los NPCs de todos los mapas desde los archivos .Inf del VB6.

Lee los archivos .Inf del servidor VB6 y extrae:
- NPCs fijos en cada tile (bit 2 del flag)
- Guarda la información en map_npcs.toml

Formato del archivo .Inf:
- Header: Double (8 bytes) + Integer (2 bytes)
- Para cada tile (100x100):
  - Flags (1 byte)
    - Bit 1: TileExit presente
    - Bit 2: NPC en el tile → Integer (NPC número)
    - Bit 4: Objeto en el tile → dos Integer (ObjIndex, Amount)
"""

import re
import struct
import tomllib
from pathlib import Path
from typing import Any

# Constantes
INT16_SIZE = 2
MAP_SIZE = 100  # 100x100 tiles


def read_map_npcs(inf_filepath: Path) -> list[dict[str, Any]]:
    """Lee un archivo .inf y extrae los NPCs del mapa.

    Args:
        inf_filepath: Ruta al archivo .inf a leer

    Returns:
        Lista de diccionarios con información de NPCs: [{"npc_id": int, "x": int, "y": int}]
    """
    npcs: list[dict[str, Any]] = []

    try:
        with inf_filepath.open("rb") as f:
            # Header .inf: Double (8 bytes) + Integer (2 bytes)
            f.seek(8 + INT16_SIZE)

            # Leer el mapa de 100x100 tiles
            for y in range(1, MAP_SIZE + 1):
                for x in range(1, MAP_SIZE + 1):
                    # Leer flags (1 byte)
                    flags_raw = f.read(1)
                    if not flags_raw:
                        break

                    flags = struct.unpack("B", flags_raw)[0]

                    # Bit 1: TileExit presente (3 integers: to_map, to_x, to_y)
                    if flags & 1:
                        f.read(INT16_SIZE * 3)  # Saltar datos de exit

                    # Bit 2: NPC en el tile → un Integer (NPC número)
                    if flags & 2:
                        npc_id_bytes = f.read(INT16_SIZE)
                        if len(npc_id_bytes) >= INT16_SIZE:
                            npc_id = struct.unpack("<H", npc_id_bytes)[0]
                            if npc_id > 0:
                                npcs.append({"npc_id": npc_id, "x": x, "y": y})

                    # Bit 4: Objeto en el tile → dos Integer (ObjIndex, Amount)
                    if flags & 4:
                        f.read(INT16_SIZE * 2)  # Saltar datos de objeto

                if not flags_raw:
                    break

    except (OSError, struct.error) as e:
        print(f"⚠️  Error leyendo {inf_filepath.name}: {e}")
        return []

    return npcs


def get_map_name(map_id: int) -> str:
    """Retorna el nombre del mapa según el ID.

    Args:
        map_id: ID del mapa

    Returns:
        Nombre del mapa o "Mapa {id}" si no se conoce
    """
    # Nombres conocidos (simplificado, se puede expandir)
    map_names: dict[int, str] = {
        1: "Ullathorpe",
        34: "Nix",
        46: "Banderbill",
        58: "Lindos",
    }

    return map_names.get(map_id, f"Mapa {map_id}")


def get_default_direction() -> int:
    """Retorna la dirección por defecto para NPCs (3 = Sur)."""
    return 3


def load_existing_map_npcs(toml_path: Path) -> dict[str, Any]:
    """Carga el archivo map_npcs.toml existente.

    Args:
        toml_path: Ruta al archivo map_npcs.toml

    Returns:
        Diccionario con los datos existentes o estructura vacía
    """
    if not toml_path.exists():
        return {"map_npcs": {}}

    try:
        with toml_path.open("rb") as f:
            data = tomllib.load(f)
            return data
    except Exception as e:
        print(f"⚠️  Error cargando {toml_path}: {e}")
        return {"map_npcs": {}}


def merge_npcs_to_map_data(
    map_id: int, npcs: list[dict[str, Any]], existing_data: dict[str, Any]
) -> None:
    """Agrega NPCs extraídos al diccionario de datos del mapa.

    Args:
        map_id: ID del mapa
        npcs: Lista de NPCs extraídos
        existing_data: Diccionario con datos existentes (se modifica in-place)
    """
    map_key = str(map_id)

    # Inicializar estructura del mapa si no existe
    if "map_npcs" not in existing_data:
        existing_data["map_npcs"] = {}

    if map_key not in existing_data["map_npcs"]:
        existing_data["map_npcs"][map_key] = {
            "name": get_map_name(map_id),
            "description": f"NPCs extraídos del mapa {map_id}",
            "spawn_points": [],
        }

    # Obtener spawns existentes para evitar duplicados
    existing_spawns = {
        (sp.get("x"), sp.get("y"), sp.get("npc_id"))
        for sp in existing_data["map_npcs"][map_key].get("spawn_points", [])
    }

    # Agregar NPCs nuevos
    for npc in npcs:
        npc_key = (npc["x"], npc["y"], npc["npc_id"])
        if npc_key not in existing_spawns:
            existing_data["map_npcs"][map_key]["spawn_points"].append(
                {
                    "npc_id": npc["npc_id"],
                    "x": npc["x"],
                    "y": npc["y"],
                    "direction": get_default_direction(),
                }
            )


def write_map_npcs_toml(data: dict[str, Any], output_path: Path) -> None:
    """Escribe los datos de NPCs en formato TOML.

    Args:
        data: Diccionario con los datos de NPCs por mapa
        output_path: Ruta donde guardar el archivo
    """
    lines: list[str] = []
    lines.append("# Configuración de spawns de NPCs en mapas")
    lines.append("# Define qué NPCs aparecen en qué mapas y en qué posiciones")
    lines.append("")
    lines.append("[map_npcs]")
    lines.append("")

    # Ordenar mapas por ID
    if "map_npcs" in data:
        sorted_maps = sorted(data["map_npcs"].items(), key=lambda x: int(x[0]))

        for map_id, map_data in sorted_maps:
            # Sección del mapa
            lines.append(f"# Mapa {map_id} - {map_data.get('name', 'Mapa ' + map_id)}")
            lines.append(f"[map_npcs.{map_id}]")
            lines.append(f'name = "{map_data.get("name", "Mapa " + str(map_id))}"')
            lines.append(f'description = "{map_data.get("description", "")}"')
            lines.append("")

            # Spawn points fijos
            spawn_points = map_data.get("spawn_points", [])
            if spawn_points:
                lines.append("# Spawn points fijos")
                for sp in spawn_points:
                    lines.append("[[map_npcs." + map_id + ".spawn_points]]")
                    lines.append(f"npc_id = {sp.get('npc_id', 0)}")
                    lines.append(f"x = {sp.get('x', 0)}")
                    lines.append(f"y = {sp.get('y', 0)}")
                    lines.append(f"direction = {sp.get('direction', 3)}")
                    lines.append("")

            # Random spawns (si existen)
            random_spawns = map_data.get("random_spawns", [])
            if random_spawns:
                for rs in random_spawns:
                    lines.append("[[map_npcs." + map_id + ".random_spawns]]")
                    lines.append(f'npc_type = "{rs.get("npc_type", "hostile")}"')
                    lines.append(f"count = {rs.get('count', 1)}")
                    area = rs.get("area", {})
                    lines.append(
                        f'area = {{x1 = {area.get("x1", 0)}, y1 = {area.get("y1", 0)}, '
                        f'x2 = {area.get("x2", 0)}, y2 = {area.get("y2", 0)}}}'
                    )
                    lines.append("")

            lines.append("")

    # Guardar archivo
    with output_path.open("w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"✅ Archivo guardado: {output_path}")


def main() -> None:
    """Función principal para extraer todos los NPCs de todos los mapas."""
    # Directorios
    vb6_maps_dir = Path(
        "clientes/ArgentumOnline0.13.3-Cliente-Servidor/server/WorldBackup"
    )
    output_file = Path("data/map_npcs.toml")

    if not vb6_maps_dir.exists():
        print(f"❌ No existe el directorio: {vb6_maps_dir}")
        return

    print("🔍 Extrayendo NPCs desde archivos .Inf del servidor VB6...")
    print(f"📁 Directorio: {vb6_maps_dir}")

    # Cargar datos existentes
    existing_data = load_existing_map_npcs(output_file)

    # Buscar todos los archivos .Inf
    inf_files = sorted(vb6_maps_dir.glob("Mapa*.Inf"))
    print(f"📊 Encontrados {len(inf_files)} archivos .Inf")

    total_npcs = 0
    maps_with_npcs = 0

    for inf_file in inf_files:
        # Extraer ID del mapa del nombre del archivo
        try:
            map_id = int(re.search(r"Mapa(\d+)", inf_file.stem).group(1))  # type: ignore[union-attr]
        except (ValueError, AttributeError):
            print(f"⚠️  No se pudo extraer ID del mapa desde: {inf_file.name}")
            continue

        # Extraer NPCs
        npcs = read_map_npcs(inf_file)

        if npcs:
            merge_npcs_to_map_data(map_id, npcs, existing_data)
            total_npcs += len(npcs)
            maps_with_npcs += 1
            print(
                f"✅ Mapa {map_id} ({get_map_name(map_id)}): "
                f"{len(npcs)} NPCs extraídos"
            )
        else:
            print(f"⚪ Mapa {map_id} ({get_map_name(map_id)}): Sin NPCs")

    # Guardar archivo actualizado
    write_map_npcs_toml(existing_data, output_file)

    print("\n📊 Resumen:")
    print(f"   - Archivos .Inf procesados: {len(inf_files)}")
    print(f"   - Mapas con NPCs: {maps_with_npcs}")
    print(f"   - Total de NPCs extraídos: {total_npcs}")
    print(f"\n✅ Proceso completado. Archivo guardado en {output_file}")


if __name__ == "__main__":
    main()

