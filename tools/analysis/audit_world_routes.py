"""Inventario reproducible de todos los mapas, salidas y pares dirigidos."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import defaultdict, deque
from pathlib import Path
from typing import Any

from src.runtime_paths import maps_dir
from src.services.map.map_bulk_resources_loader import load_map_resources

Route = tuple[int, int, int, int, int, int]
DIRECTIONS = ((1, 0, -1), (2, 1, 0), (3, 0, 1), (4, -1, 0))


def read_rows(path: Path) -> list[dict[str, Any]]:
    """Lee NDJSON estrictamente, sin esconder una fila incompleta.

    Returns:
        Filas originales del archivo.

    Raises:
        ValueError: Si una fila no es un objeto JSON.
    """
    rows = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            message = f"{path}:{number}: se esperaba un objeto"
            raise ValueError(message)
        rows.append(row)
    return rows


def integer(row: dict[str, Any], key: str) -> int:
    """Exige enteros reales para no convertir coordenadas inválidas.

    Returns:
        Valor entero de la clave.

    Raises:
        ValueError: Si falta la clave, es booleana o no es entera.
    """
    value = row.get(key)
    if not isinstance(value, int) or isinstance(value, bool):
        message = f"Campo {key} inválido: {value!r}"
        raise ValueError(message)
    return value


def graph_distances(adjacency: dict[int, set[int]], start: int) -> dict[int, int]:
    """Calcula saltos del grafo; no certifica caminos dentro de cada mapa.

    Returns:
        Distancia mínima a cada mapa alcanzable, incluido el origen.
    """
    distances = {start: 0}
    pending = deque([start])
    while pending:
        at = pending.popleft()
        for other in sorted(adjacency[at] - distances.keys()):
            distances[other] = distances[at] + 1
            pending.append(other)
    return distances


def inspect_world(
    source: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    """Revisa cada casilla y todos los pares ordenados del conjunto de mapas.

    Returns:
        Informe determinista, filas de salidas y matriz completa de pares.

    Raises:
        ValueError: Si faltan datos, hay mapas repetidos o referencias inválidas.
    """
    metadata: dict[int, dict[str, Any]] = {}
    routes: list[Route] = []
    hashes = {}
    duplicates = []
    seen: set[tuple[int, int, int]] = set()
    for prefix in ("metadata", "transitions", "blocked", "objects"):
        paths = sorted(source.glob(f"{prefix}_*.json"))
        if not paths:
            message = f"Faltan archivos {prefix} en {source}"
            raise ValueError(message)
        for path in paths:
            hashes[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
            if prefix not in {"metadata", "transitions"}:
                continue
            for row in read_rows(path):
                if prefix == "metadata":
                    identity = integer(row, "i")
                    if identity in metadata:
                        message = f"Mapa repetido: {identity}"
                        raise ValueError(message)
                    metadata[identity] = row
                    continue
                origin = integer(row, "from_map")
                for exit_row in row["exits"]:
                    key = (origin, integer(exit_row, "x"), integer(exit_row, "y"))
                    if key in seen:
                        duplicates.append(list(key))
                    seen.add(key)
                    routes.append(
                        (*key, *(integer(exit_row, k) for k in ("to_map", "to_x", "to_y")))
                    )
    blocked, water, *_rest = load_map_resources(
        sorted(source.glob("blocked_*.json")), sorted(source.glob("objects_*.json"))
    )
    if not metadata:
        message = "No hay mapas en metadata"
        raise ValueError(message)
    solid = {identity: tiles - water.get(identity, set()) for identity, tiles in blocked.items()}
    index = {route[:3]: route[3:] for route in routes}
    pairs: dict[tuple[int, int], list[Route]] = defaultdict(list)
    for route in routes:
        pairs[route[0], route[3]].append(route)
    exits = []
    findings: dict[str, list[list[int]]] = defaultdict(list)
    for route in sorted(routes):
        origin, x, y, target, tx, ty = route
        source_water = water.get(origin, set())
        destination_water = water.get(target, set())
        reasons = []
        valid = origin in metadata and target in metadata
        if valid:
            valid = all(
                1 <= value <= integer(metadata[identity], bound)
                for identity, bound, value in (
                    (origin, "w", x),
                    (origin, "h", y),
                    (target, "w", tx),
                    (target, "h", ty),
                )
            )
        if not valid:
            reasons.append("invalid_reference_or_coordinate")
        approaches = [
            (x - dx, y - dy, heading)
            for heading, dx, dy in DIRECTIONS
            if origin in metadata
            and 1 <= x - dx <= metadata[origin]["w"]
            and 1 <= y - dy <= metadata[origin]["h"]
        ]
        foot = [
            point
            for point in approaches
            if point[:2] not in blocked.get(origin, set()) and (origin, *point[:2]) not in index
        ]
        boat = [
            point
            for point in approaches
            if point[:2] in source_water and (origin, *point[:2]) not in index
        ]
        if (tx, ty) in solid.get(target, set()):
            reasons.append("solid_destination")
        if (x, y) in solid.get(origin, set()):
            reasons.append("source_requires_portal_override")
        if not foot and not boat:
            reasons.append("no_static_cardinal_approach")
        if (target, tx, ty) in index:
            reasons.append("landing_on_another_exit")
        if (target, origin) not in pairs:
            reasons.append("no_direct_reverse_pair")
        if ((x, y) in source_water) != ((tx, ty) in destination_water):
            reasons.append("water_land_mismatch")
        for reason in reasons:
            findings[reason].append(list(route))
        exits.append(
            {
                "from_map": origin,
                "x": x,
                "y": y,
                "to_map": target,
                "to_x": tx,
                "to_y": ty,
                "source_water": (x, y) in source_water,
                "destination_water": (tx, ty) in destination_water,
                "valid_cardinal_approaches": len(approaches),
                "foot_approaches": foot,
                "boat_approaches": boat,
                "findings": reasons,
            }
        )
    adjacency = {identity: set() for identity in metadata}
    for origin, target in pairs:
        if origin in adjacency and target in adjacency:
            adjacency[origin].add(target)
    reachable = {identity: graph_distances(adjacency, identity) for identity in metadata}
    matrix = [
        {
            "from_map": origin,
            "to_map": target,
            "direct": (origin, target) in pairs,
            "graph_hops": reachable[origin].get(target, ""),
        }
        for origin in sorted(metadata)
        for target in sorted(metadata)
    ]
    incoming = {target for targets in adjacency.values() for target in targets}
    summary = {
        "maps": len(metadata),
        "exit_tiles": len(routes),
        "directed_pairs": len(pairs),
        "intermap_pairs": sum(origin != target for origin, target in pairs),
        "cardinal_inputs": sum(row["valid_cardinal_approaches"] for row in exits),
        "all_ordered_map_pairs": len(matrix),
        "reachable_ordered_pairs_including_self": sum(len(v) for v in reachable.values()),
        "duplicate_sources": sorted(duplicates),
        "findings": {key: len(value) for key, value in sorted(findings.items())},
        "maps_without_exits": sorted(identity for identity in metadata if not adjacency[identity]),
        "maps_without_entries": sorted(metadata.keys() - incoming),
    }
    if 1 in reachable:
        summary["not_graph_reachable_from_1"] = sorted(metadata.keys() - reachable[1].keys())
        summary["reachable_from_1_without_graph_path_back"] = sorted(
            identity for identity in reachable[1] if 1 not in reachable[identity]
        )
    report = {
        "version": 1,
        "coverage": "Static data and graph only; no TCP or graphical gameplay assertion",
        "summary": summary,
        "sources": dict(sorted(hashes.items())),
        "maps": {
            str(identity): {
                "metadata": metadata[identity],
                "exits": sum(
                    len(value) for (origin, _), value in pairs.items() if origin == identity
                ),
                "destinations": sorted(adjacency[identity]),
            }
            for identity in sorted(metadata)
        },
        "pairs": [
            {
                "from_map": origin,
                "to_map": target,
                "exit_tiles": len(value),
                "direct_reverse": (target, origin) in pairs,
            }
            for (origin, target), value in sorted(pairs.items())
        ],
        "findings": dict(sorted(findings.items())),
    }
    return report, exits, matrix


def main() -> int:
    """Genera evidencia o verifica que el inventario versionado siga vigente.

    Returns:
        Cero si los datos y el inventario son válidos; uno si difieren.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=maps_dir())
    parser.add_argument("--output", type=Path)
    parser.add_argument("--check", type=Path)
    parser.add_argument("--roles", type=Path)
    parser.add_argument("--water-routes", type=Path)
    args = parser.parse_args()
    report, exits, matrix = inspect_world(args.source)
    if args.roles:
        from tools.analysis.world_roles import review_roles

        report["roles"] = review_roles(args.source, args.roles)
    if args.water_routes:
        from tools.analysis.water_routes import classify

        if json.loads(args.water_routes.read_text()) != classify(exits):
            raise ValueError("La clasificación de agua/tierra no coincide con las salidas actuales")
        report["water_policy"] = {
            "candidates": len(classify(exits)["routes"]),
            "manifest_sha256": hashlib.sha256(args.water_routes.read_bytes()).hexdigest(),
        }
    if args.output:
        args.output.mkdir(parents=True, exist_ok=True)
        (args.output / "audit.json").write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        with (args.output / "exits.jsonl").open("w", encoding="utf-8") as file:
            for row in exits:
                file.write(json.dumps(row, ensure_ascii=False) + "\n")
        with (args.output / "map-pair-matrix.csv").open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=["from_map", "to_map", "direct", "graph_hops"])
            writer.writeheader()
            writer.writerows(matrix)
    matches = not args.check or json.loads(args.check.read_text(encoding="utf-8")) == report
    print(json.dumps({**report["summary"], "inventory_matches": matches}, indent=2))
    hard_errors = bool(
        report["summary"]["duplicate_sources"]
        or report["findings"].get("invalid_reference_or_coordinate")
        or report["findings"].get("solid_destination")
    )
    return 0 if matches and not hard_errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
