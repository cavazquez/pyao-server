"""Consultas puras sobre la estructura de datos de MapResourcesService.

Separa la lógica de lectura de tiles (blocked, water, signs, etc.) del cargador
y del ciclo de vida del servicio. Tipado alineado con `MapResourcesService.resources`,
`signs` y `doors`.
"""

from __future__ import annotations

ResourcesMap = dict[str, dict[str, set[tuple[int, int]]]]
SignsMap = dict[str, dict[tuple[int, int], int]]
DoorsMap = dict[str, dict[tuple[int, int], int]]


def map_key(map_id: int) -> str:
    return f"map_{map_id}"


def tile_in_required_layer(
    resources: ResourcesMap,
    map_id: int,
    layer: str,
    x: int,
    y: int,
) -> bool:
    """Capas que siempre existen cuando el mapa está cargado (blocked, water, trees, mines)."""
    mk = map_key(map_id)
    if mk not in resources:
        return False
    return (x, y) in resources[mk][layer]


def tile_in_optional_layer(
    resources: ResourcesMap,
    map_id: int,
    layer: str,
    x: int,
    y: int,
) -> bool:
    """Capas que pueden faltar (anvils, forges)."""
    mk = map_key(map_id)
    if mk not in resources:
        return False
    return (x, y) in resources[mk].get(layer, set())


def get_resource_counts(
    resources: ResourcesMap,
    signs: SignsMap,
    doors: DoorsMap,
    map_id: int,
) -> dict[str, int]:
    """Conteos por tipo para un mapa."""
    mk = map_key(map_id)
    if mk not in resources:
        return {"water": 0, "trees": 0, "mines": 0}

    signs_count = len(signs.get(mk, {}))
    doors_count = len(doors.get(mk, {}))
    anvils_count = len(resources[mk].get("anvils", set()))
    forges_count = len(resources[mk].get("forges", set()))

    return {
        "water": len(resources[mk]["water"]),
        "trees": len(resources[mk]["trees"]),
        "mines": len(resources[mk]["mines"]),
        "anvils": anvils_count,
        "forges": forges_count,
        "signs": signs_count,
        "doors": doors_count,
    }


def get_sign_at(signs: SignsMap, map_id: int, x: int, y: int) -> int | None:
    mk = map_key(map_id)
    if mk not in signs:
        return None
    return signs[mk].get((x, y))


def get_door_at(doors: DoorsMap, map_id: int, x: int, y: int) -> int | None:
    mk = map_key(map_id)
    if mk not in doors:
        return None
    return doors[mk].get((x, y))
