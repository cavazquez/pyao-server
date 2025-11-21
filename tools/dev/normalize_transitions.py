#!/usr/bin/env python3
"""Normaliza archivos transitions_XXX-XXX.json en map_data/.

Este script filtra y ordena las transiciones de mapa generadas desde VB6,
manteniendo solo aquellas que son válidas para el servidor Python:

- `from_map` debe estar en el rango [1, 290].
- `to_map` debe estar en el rango [1, 290].
- `to_x` y `to_y` deben estar en el rango [1, 100].

También elimina grupos sin exits válidos y ordena:
- Los grupos por `from_map`.
- Los exits dentro de cada grupo por (y, x) para facilitar debugging.

Antes de sobreescribir cada archivo, crea un backup con la extensión
`.backup` si aún no existe.

Uso sugerido:

    uv run tools/normalize_transitions.py

"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

MAX_MAP_ID = 290
MAX_COORDINATE = 100


def _coerce_int(value: Any) -> int | None:
    """Convierte un valor a int, devolviendo None si no es posible."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None
        try:
            return int(value)
        except ValueError:
            return None
    return None


def normalize_transitions_file(path: Path) -> None:
    """Normaliza un archivo transitions_XXX-XXX.json.

    - Filtra grupos y exits inválidos.
    - Ordena grupos por from_map y exits por (y, x).
    - Crea un backup `.backup` si no existe.
    """

    try:
        raw_text = path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f" No se pudo leer {path}: {exc}")
        return

    # Soportar tanto JSON tradicional como NDJSON (una transición por línea)
    transitions: list[dict[str, Any]] = []

    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError:
        # NDJSON: cada línea es un grupo de transiciones
        for line_number, line in enumerate(raw_text.splitlines(), start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                obj = json.loads(stripped)
            except json.JSONDecodeError as exc:
                print(
                    f" JSON inválido en {path} línea {line_number}: {exc}"
                )
                continue
            if isinstance(obj, dict):
                transitions.append(obj)

        if not transitions:
            print(f"  {path} no contiene transiciones válidas, se omite")
            return

    else:
        raw_transitions = data.get("transitions")
        if not isinstance(raw_transitions, list):
            print(f"  {path} no tiene una lista 'transitions', se omite")
            return
        transitions = [g for g in raw_transitions if isinstance(g, dict)]

    new_groups: list[dict[str, Any]] = []

    for group in transitions:
        if not isinstance(group, dict):
            continue

        from_map = _coerce_int(group.get("from_map"))
        if from_map is None or not (1 <= from_map <= MAX_MAP_ID):
            continue

        exits = group.get("exits", [])
        if not isinstance(exits, list):
            exits = []

        new_exits: list[dict[str, Any]] = []
        for exit_data in exits:
            if not isinstance(exit_data, dict):
                continue

            x = _coerce_int(exit_data.get("x"))
            y = _coerce_int(exit_data.get("y"))
            to_map = _coerce_int(exit_data.get("to_map"))
            to_x = _coerce_int(exit_data.get("to_x"))
            to_y = _coerce_int(exit_data.get("to_y"))

            if (
                x is None
                or y is None
                or to_map is None
                or to_x is None
                or to_y is None
            ):
                continue

            # Aplicar mismas restricciones que MapManager._load_map_transitions
            if not (1 <= to_map <= MAX_MAP_ID):
                continue
            if not (1 <= to_x <= MAX_COORDINATE and 1 <= to_y <= MAX_COORDINATE):
                continue

            # Mantener el exit tal cual, solo asegurando que x/y/to_* sean ints
            normalized_exit = dict(exit_data)
            normalized_exit["x"] = x
            normalized_exit["y"] = y
            normalized_exit["to_map"] = to_map
            normalized_exit["to_x"] = to_x
            normalized_exit["to_y"] = to_y
            new_exits.append(normalized_exit)

        if not new_exits:
            continue

        # Ordenar exits por (y, x) para facilitar revisión visual
        new_exits.sort(key=lambda e: (e["y"], e["x"]))

        normalized_group = dict(group)
        normalized_group["from_map"] = from_map
        normalized_group["exits"] = new_exits
        new_groups.append(normalized_group)

    if not new_groups:
        print(f"  {path}: sin transiciones válidas, se deja sin cambios")
        return

    # Ordenar grupos por from_map
    new_groups.sort(key=lambda g: g.get("from_map", 0))

    # Crear backup si no existe aún
    backup_path = path.with_suffix(path.suffix + ".backup")
    if not backup_path.exists():
        try:
            backup_path.write_text(raw_text, encoding="utf-8")
            print(f" Backup creado: {backup_path}")
        except OSError as exc:
            print(f"  No se pudo crear backup {backup_path}: {exc}")

    # Escribir archivo normalizado en formato NDJSON (un grupo por línea)
    try:
        with path.open("w", encoding="utf-8") as f:
            for group in new_groups:
                f.write(json.dumps(group, ensure_ascii=False) + "\n")

        total_exits = sum(len(g["exits"]) for g in new_groups)
        print(
            f" Normalizado {path.name}: {len(new_groups)} mapas, {total_exits} exits válidos"
        )
    except OSError as exc:
        print(f" Error escribiendo {path}: {exc}")


def main() -> None:
    base_dir = Path("map_data")
    if not base_dir.exists():
        print(" Directorio map_data/ no encontrado")
        return

    files = sorted(base_dir.glob("transitions_*.json"))
    if not files:
        print("⚪ No se encontraron archivos transitions_*.json en map_data/")
        return

    print("🔍 Normalizando archivos de transiciones en map_data/...")
    for path in files:
        normalize_transitions_file(path)

    print("\n✅ Proceso de normalización completado.")


if __name__ == "__main__":
    main()
