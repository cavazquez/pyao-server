# ruff: noqa: DOC201, PLW2901, PLR2004, PLC0415, SIM102
"""Herramienta para validar transiciones de mapas.

Detecta:
- Transiciones a mapas que no existen
- Transiciones a coordenadas fuera de rango
- Transiciones que llevan a tiles bloqueados
- Transiciones unidireccionales (sin retorno)

Uso:
    uv run python -m tools.validation.check_map_transitions
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

MAP_DATA_DIR = Path("map_data")
MAP_WIDTH = 100
MAP_HEIGHT = 100


@dataclass
class Transition:
    """Representa una transición de mapa."""

    from_map: int
    from_x: int
    from_y: int
    to_map: int
    to_x: int
    to_y: int


@dataclass
class ValidationResult:
    """Resultado de la validación."""

    total_transitions: int = 0
    valid_transitions: int = 0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        """Retorna True si no hay errores."""
        return len(self.errors) == 0


def load_transitions(map_data_dir: Path = MAP_DATA_DIR) -> list[Transition]:
    """Carga todas las transiciones desde los archivos JSON."""
    transitions: list[Transition] = []

    for transitions_file in sorted(map_data_dir.glob("transitions_*.json")):
        with transitions_file.open(encoding="utf-8") as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    from_map = data.get("from_map")
                    exits = data.get("exits", [])
                    for exit_data in exits:
                        transitions.append(
                            Transition(
                                from_map=from_map,
                                from_x=exit_data["x"],
                                from_y=exit_data["y"],
                                to_map=exit_data["to_map"],
                                to_x=exit_data["to_x"],
                                to_y=exit_data["to_y"],
                            )
                        )
                except (json.JSONDecodeError, KeyError):
                    continue

    return transitions


def load_existing_maps(map_data_dir: Path = MAP_DATA_DIR) -> set[int]:
    """Obtiene IDs de mapas que existen."""
    map_ids: set[int] = set()

    for blocked_file in map_data_dir.glob("blocked_*.json"):
        with blocked_file.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    map_ids.add(data["m"])
                except (json.JSONDecodeError, KeyError):
                    continue

    return map_ids


def load_blocked_tiles(
    map_data_dir: Path = MAP_DATA_DIR,
) -> dict[int, set[tuple[int, int]]]:
    """Carga tiles bloqueados por mapa."""
    blocked: dict[int, set[tuple[int, int]]] = {}

    for blocked_file in map_data_dir.glob("blocked_*.json"):
        with blocked_file.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    map_id = data["m"]
                    x = data["x"]
                    y = data["y"]
                    if map_id not in blocked:
                        blocked[map_id] = set()
                    blocked[map_id].add((x, y))
                except (json.JSONDecodeError, KeyError):
                    continue

    return blocked


def validate_transitions(
    map_data_dir: Path = MAP_DATA_DIR,
    check_blocked: bool = True,
    check_bidirectional: bool = True,
) -> ValidationResult:
    """Valida todas las transiciones de mapas.

    Args:
        map_data_dir: Directorio con datos de mapas.
        check_blocked: Si verificar que destinos no estén bloqueados.
        check_bidirectional: Si verificar que existan transiciones de retorno.

    Returns:
        ValidationResult con errores y advertencias encontrados.
    """
    result = ValidationResult()

    print("Cargando datos de mapas...")
    transitions = load_transitions(map_data_dir)
    existing_maps = load_existing_maps(map_data_dir)
    blocked_tiles = load_blocked_tiles(map_data_dir) if check_blocked else {}

    result.total_transitions = len(transitions)
    print(f"  {len(transitions)} transiciones encontradas")
    print(f"  {len(existing_maps)} mapas con datos")

    print("\nValidando transiciones...")
    for t in transitions:
        # 1. Verificar que mapa destino existe
        if t.to_map not in existing_maps:
            result.errors.append(
                f"Mapa {t.from_map} ({t.from_x},{t.from_y}) -> Mapa {t.to_map} NO EXISTE"
            )
            continue

        # 2. Verificar coordenadas en rango
        if not (0 <= t.to_x < MAP_WIDTH and 0 <= t.to_y < MAP_HEIGHT):
            result.errors.append(
                f"Mapa {t.from_map} ({t.from_x},{t.from_y}) -> Mapa {t.to_map} "
                f"coordenadas fuera de rango ({t.to_x},{t.to_y})"
            )
            continue

        # 3. Verificar que destino no esté bloqueado
        if check_blocked and t.to_map in blocked_tiles:
            if (t.to_x, t.to_y) in blocked_tiles[t.to_map]:
                result.warnings.append(
                    f"Mapa {t.from_map} ({t.from_x},{t.from_y}) -> Mapa {t.to_map} "
                    f"destino bloqueado ({t.to_x},{t.to_y})"
                )

        # 4. Verificar transición de retorno (bidireccional)
        if check_bidirectional:
            has_return = False
            for rt in transitions:
                if (
                    rt.from_map == t.to_map
                    and abs(rt.from_x - t.to_x) <= 3
                    and abs(rt.from_y - t.to_y) <= 3
                    and rt.to_map == t.from_map
                ):
                    has_return = True
                    break

            if not has_return:
                result.warnings.append(
                    f"Mapa {t.from_map} ({t.from_x},{t.from_y}) -> Mapa {t.to_map} "
                    f"sin transicion de retorno"
                )

        result.valid_transitions += 1

    return result


def main() -> None:
    """Punto de entrada CLI."""
    import argparse

    parser = argparse.ArgumentParser(description="Valida transiciones de mapas")
    parser.add_argument("--map-data", type=Path, default=MAP_DATA_DIR)
    parser.add_argument(
        "--no-blocked", action="store_true", help="No verificar tiles bloqueados"
    )
    parser.add_argument(
        "--no-bidirectional", action="store_true", help="No verificar retornos"
    )
    parser.add_argument("--errors-only", action="store_true", help="Solo mostrar errores")

    args = parser.parse_args()

    result = validate_transitions(
        map_data_dir=args.map_data,
        check_blocked=not args.no_blocked,
        check_bidirectional=not args.no_bidirectional,
    )

    print("\n" + "=" * 60)
    print("  RESULTADO DE VALIDACION")
    print("=" * 60)
    print(f"  Total transiciones: {result.total_transitions}")
    print(f"  Validas: {result.valid_transitions}")
    print(f"  Errores: {len(result.errors)}")
    print(f"  Advertencias: {len(result.warnings)}")

    if result.errors:
        print("\n[ERROR] ERRORES (transiciones rotas):")
        for error in result.errors[:20]:
            print(f"   - {error}")
        if len(result.errors) > 20:
            print(f"   ... y {len(result.errors) - 20} mas")

    if result.warnings and not args.errors_only:
        print("\n[WARN] ADVERTENCIAS:")
        for warning in result.warnings[:20]:
            print(f"   - {warning}")
        if len(result.warnings) > 20:
            print(f"   ... y {len(result.warnings) - 20} mas")

    if result.is_valid:
        print("\n[OK] Todas las transiciones son validas")
    else:
        print(f"\n[ERROR] Se encontraron {len(result.errors)} errores")


if __name__ == "__main__":
    main()
