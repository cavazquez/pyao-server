# ruff: noqa: DOC201, PLW2901
"""Herramienta para corregir transiciones rotas en map_data/.

Elimina transiciones que apuntan a mapas inexistentes.

Uso:
    uv run python -m tools.validation.fix_broken_transitions --dry-run  # Ver cambios
    uv run python -m tools.validation.fix_broken_transitions            # Aplicar cambios
"""

from __future__ import annotations

import argparse
import json
import glob
from pathlib import Path


def get_existing_maps(map_data_dir: Path) -> set[int]:
    """Obtiene IDs de mapas que existen."""
    maps = set()
    for f in glob.glob(str(map_data_dir / "blocked_*.json")):
        with open(f, encoding="utf-8") as file:
            for line in file:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    maps.add(data["m"])
                except (json.JSONDecodeError, KeyError):
                    continue
    return maps


def fix_transitions(
    map_data_dir: Path,
    dry_run: bool = True,
) -> dict[str, int]:
    """Corrige transiciones rotas.

    Args:
        map_data_dir: Directorio con datos de mapas.
        dry_run: Si True, solo muestra cambios sin aplicarlos.

    Returns:
        Estadísticas de correcciones.
    """
    stats = {
        "files_processed": 0,
        "files_modified": 0,
        "transitions_removed": 0,
        "transitions_kept": 0,
    }

    existing_maps = get_existing_maps(map_data_dir)
    print(f"Mapas existentes: {len(existing_maps)}")

    for transitions_file in sorted(glob.glob(str(map_data_dir / "transitions_*.json"))):
        stats["files_processed"] += 1
        file_path = Path(transitions_file)
        
        new_lines = []
        file_modified = False

        with open(file_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                
                try:
                    data = json.loads(line)
                    original_exits = data.get("exits", [])
                    
                    # Filtrar transiciones a mapas inexistentes
                    valid_exits = [
                        exit_data
                        for exit_data in original_exits
                        if exit_data.get("to_map") in existing_maps
                    ]
                    
                    removed = len(original_exits) - len(valid_exits)
                    if removed > 0:
                        file_modified = True
                        stats["transitions_removed"] += removed
                        print(
                            f"  {file_path.name}: Mapa {data['from_map']} "
                            f"- removidas {removed} transiciones"
                        )
                    
                    stats["transitions_kept"] += len(valid_exits)
                    
                    # Solo incluir si tiene salidas válidas
                    if valid_exits:
                        data["exits"] = valid_exits
                        new_lines.append(json.dumps(data, ensure_ascii=False))
                    
                except (json.JSONDecodeError, KeyError):
                    # Mantener líneas que no se pueden parsear
                    new_lines.append(line)

        if file_modified:
            stats["files_modified"] += 1
            if not dry_run:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write("\n".join(new_lines) + "\n")
                print(f"  ✓ {file_path.name} actualizado")

    return stats


def main() -> None:
    """Punto de entrada CLI."""
    parser = argparse.ArgumentParser(
        description="Corrige transiciones rotas en map_data/"
    )
    parser.add_argument(
        "--map-data",
        type=Path,
        default=Path("map_data"),
        help="Directorio con datos de mapas",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Solo mostrar cambios sin aplicarlos",
    )

    args = parser.parse_args()

    print("=" * 50)
    print("  Corrección de Transiciones Rotas")
    print("=" * 50)
    
    if args.dry_run:
        print("MODO: Dry run (sin cambios)")
    else:
        print("MODO: Aplicando cambios")
    print()

    stats = fix_transitions(args.map_data, dry_run=args.dry_run)

    print()
    print("=" * 50)
    print("  Resumen")
    print("=" * 50)
    print(f"  Archivos procesados: {stats['files_processed']}")
    print(f"  Archivos modificados: {stats['files_modified']}")
    print(f"  Transiciones eliminadas: {stats['transitions_removed']}")
    print(f"  Transiciones válidas: {stats['transitions_kept']}")
    
    if args.dry_run and stats["transitions_removed"] > 0:
        print()
        print("Ejecuta sin --dry-run para aplicar los cambios")


if __name__ == "__main__":
    main()


