"""Comprueba el alcance jugable y las salidas dirigidas sin inventar conexiones."""

from collections import defaultdict, deque
import json
from pathlib import Path
from typing import Any


def path_to(graph: dict[int, set[int]], origin: int, target: int) -> list[int]:
    """Busca una ruta real del grafo dirigido.

    Returns:
        Secuencia de mapas o lista vacía cuando no hay una ruta.
    """
    pending = deque([[origin]])
    seen = {origin}
    while pending:
        route = pending.popleft()
        if route[-1] == target:
            return route
        for neighbour in sorted(graph.get(route[-1], set())):
            if neighbour not in seen:
                seen.add(neighbour)
                pending.append([*route, neighbour])
    return []


def review_roles(source: Path, roles_path: Path) -> dict[str, Any]:
    """Exige acceso y retorno de cada mapa jugable y justifica los reservados.

    Returns:
        Matriz resumida de roles y revisión de cada par sin retorno directo.

    Raises:
        ValueError: Si hay roles ausentes, accesos a reservas o callejones no declarados.
    """
    roles = json.loads(roles_path.read_text())["maps"]
    ids = {
        int(json.loads(line)["i"])
        for path in source.glob("metadata_*.json")
        for line in path.read_text().splitlines()
        if line.strip()
    }
    if set(map(int, roles)) != ids:
        raise ValueError("El manifiesto debe declarar el rol de cada mapa")
    graph: dict[int, set[int]] = defaultdict(set)
    counts: dict[tuple[int, int], int] = defaultdict(int)
    for path in source.glob("transitions_*.json"):
        for line in path.read_text().splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            for exit_row in row["exits"]:
                a, b = row["from_map"], exit_row["to_map"]
                graph[a].add(b)
                counts[a, b] += 1
    for mid in sorted(ids):
        role = roles[str(mid)]
        if role["role"] == "playable":
            if not path_to(graph, 1, mid) or not path_to(graph, mid, 1):
                raise ValueError(f"Mapa jugable sin acceso o retorno: {mid}")
            if any(roles[str(other)]["role"] == "reserved" for other in graph[mid]):
                raise ValueError(f"Salida ordinaria hacia una reserva desde {mid}")
        elif (
            role["role"] != "reserved"
            or not role.get("reason")
            or role.get("access") != "administrative_only"
        ):
            raise ValueError(f"Reserva sin política explícita: {mid}")
    directed = []
    for (a, b), amount in sorted(counts.items()):
        if a != b and (b, a) not in counts:
            return_path = path_to(graph, b, a)
            if not return_path and roles[str(a)]["role"] == "playable":
                raise ValueError(f"Enlace jugable sin escape: {a} -> {b}")
            directed.append(
                {
                    "from": a,
                    "to": b,
                    "exit_tiles": amount,
                    "return_path": return_path,
                    "policy": "return_via_existing_directed_route"
                    if return_path
                    else "reserved_administrative_layout",
                }
            )
    return {
        "map_count": len(ids),
        "ordered_pairs": len(ids) ** 2,
        "playable": sum(r["role"] == "playable" for r in roles.values()),
        "reserved": sum(r["role"] == "reserved" for r in roles.values()),
        "one_way_pairs": directed,
        "policy": "No authored inverse links; each playable map can return to Ullathorpe through existing routes.",
    }
