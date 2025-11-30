#!/usr/bin/env python3
"""
Script para limpiar NPCs duplicados en las mismas posiciones del archivo map_npcs.toml.

Cuando múltiples NPCs están en la misma posición (mapa, x, y), solo se mantiene el primero.
"""

import tomllib
from collections import defaultdict
from pathlib import Path
from typing import Any


def clean_duplicate_spawns(toml_path: Path) -> dict[str, Any]:
    """Limpia NPCs duplicados en las mismas posiciones.

    Args:
        toml_path: Ruta al archivo map_npcs.toml

    Returns:
        Diccionario con los datos limpiados
    """
    # Cargar archivo existente
    with toml_path.open("rb") as f:
        data = tomllib.load(f)

    if "map_npcs" not in data:
        return data

    cleaned_data = {"map_npcs": {}}
    total_removed = 0

    for map_id, map_data in data["map_npcs"].items():
        spawn_points = map_data.get("spawn_points", [])
        if not spawn_points:
            # Sin spawn points, copiar tal cual
            cleaned_data["map_npcs"][map_id] = map_data
            continue

        # Agrupar por posición (x, y)
        position_spawns: dict[tuple[int, int], list[dict[str, Any]]] = defaultdict(list)

        for spawn in spawn_points:
            x = spawn.get("x")
            y = spawn.get("y")
            if x is not None and y is not None:
                position_spawns[(x, y)].append(spawn)

        # Para cada posición, mantener solo el primero
        cleaned_spawns: list[dict[str, Any]] = []
        removed_in_map = 0

        for (x, y), spawns in position_spawns.items():
            if len(spawns) > 1:
                removed_in_map += len(spawns) - 1
                print(
                    f"⚠️  Mapa {map_id} ({x},{y}): {len(spawns)} NPCs duplicados, "
                    f"manteniendo solo el primero (npc_id={spawns[0].get('npc_id')})"
                )
            cleaned_spawns.append(spawns[0])  # Mantener solo el primero

        total_removed += removed_in_map

        # Construir datos limpiados
        cleaned_data["map_npcs"][map_id] = {
            "name": map_data.get("name", f"Mapa {map_id}"),
            "description": map_data.get("description", ""),
            "spawn_points": cleaned_spawns,
        }

        # Mantener random_spawns si existen
        if "random_spawns" in map_data:
            cleaned_data["map_npcs"][map_id]["random_spawns"] = map_data["random_spawns"]

    print(f"\n📊 Resumen: {total_removed} NPCs duplicados removidos")
    return cleaned_data


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
    """Función principal para limpiar NPCs duplicados."""
    toml_path = Path("data/map_npcs.toml")

    if not toml_path.exists():
        print(f"❌ No existe el archivo: {toml_path}")
        return

    print("🔍 Limpiando NPCs duplicados en las mismas posiciones...")
    print(f"📁 Archivo: {toml_path}\n")

    # Limpiar duplicados
    cleaned_data = clean_duplicate_spawns(toml_path)

    # Guardar archivo limpiado
    write_map_npcs_toml(cleaned_data, toml_path)

    print("\n✅ Proceso completado!")


if __name__ == "__main__":
    main()

