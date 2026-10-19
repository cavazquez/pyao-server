"""Compara el contrato de generación con instancias reales, sin corregir los datos.

Los nombres de roles son indicios para revisar guardias y sacerdotes; sólo los
flags explícitos prueban una interacción. El informe nunca infiere hostilidad
a partir de que un NPC sea atacable o tenga un nombre particular.
"""

import json
import re
import tomllib
from collections import Counter, defaultdict
from dataclasses import asdict
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from src.game.map_manager import MapManager
    from src.models.npc import NPC
    from src.models.npc_catalog import NPCCatalog


MAX_SOUND_ID = 255


def roles(row: dict[str, Any]) -> list[str]:
    """Identifica servicios explícitos e indicios de rol que necesitan revisión.

    Returns:
        Roles independientes del flag de hostilidad.
    """
    result = []
    for field, role in (("es_mercader", "merchant"), ("es_banquero", "banker")):
        if row.get(field):
            result.append(role)
    name = str(row.get("nombre", row.get("name", ""))).lower()
    if "sacerdote" in name or row.get("npc_type") in {1, 9}:
        result.append("priest_hint")
    if "guardia" in name or row.get("npc_type") in {2, 8}:
        result.append("guard_hint")
    return result or ["inhabitant"]


def original_sounds(path: Path) -> dict[int, list[int]]:
    """Lee Snd1/2/3 por su número, conservando huecos y mayúsculas del DAT.

    Returns:
        Referencia histórica; no reemplaza decisiones propias del catálogo.
    """
    blocks = re.findall(
        r"\[NPC(\d+)\](.*?)(?=\[NPC\d+\]|\[INIT\]|\Z)",
        path.read_text(encoding="latin-1"),
        re.DOTALL | re.IGNORECASE,
    )
    result = {}
    for npc_id, block in blocks:
        sounds = [0, 0, 0]
        for slot, wave in re.findall(r"(?im)^\s*Snd([123])\s*=\s*(\d+)", block):
            sounds[int(slot) - 1] = int(wave)
        result[int(npc_id)] = sounds
    return result


def sound_inventory(
    catalog: NPCCatalog, client: Path | None, original: Path | None
) -> dict[str, Any]:
    """Audita silencio explícito, datos ausentes, límites de protocolo y recursos.

    Returns:
        Filas por NPC y divergencias históricas separadas del catálogo vigente.
    """
    historical = original_sounds(original) if original else {}
    rows = []
    findings = []
    for npc_id in sorted(catalog.get_all_npc_ids()):
        data = catalog.get_npc_data(npc_id) or {}
        appearance = data.get("appearance")
        configured = appearance.get("sounds") if isinstance(appearance, dict) else None
        values = list(configured[:3]) if isinstance(configured, list) else []
        waves = [*values, 0, 0, 0][:3]
        row = {
            "npc_id": npc_id,
            "configured": configured is not None,
            "waves": waves,
            "historical_waves": historical.get(npc_id),
        }
        if historical.get(npc_id) and historical[npc_id] != waves:
            findings.append({"code": "historical_sound_difference", **row})
        for slot, wave in enumerate(waves, 1):
            if not isinstance(wave, int) or not 0 <= wave <= MAX_SOUND_ID:
                findings.append({"code": "invalid_sound_id", "npc_id": npc_id, "slot": slot})
            elif wave and client and not (client / f"Assets/Sfx/{wave}.wav").is_file():
                findings.append({"code": "missing_sound_asset", "npc_id": npc_id, "wave": wave})
        rows.append(row)
    historical_missing = sorted(
        wave
        for wave in {wave for waves in historical.values() for wave in waves if wave}
        if client and not (client / f"Assets/Sfx/{wave}.wav").is_file()
    )
    return {
        "catalog": rows,
        "npcs_with_configured_sound": sum(any(cast("list[int]", row["waves"])) for row in rows),
        "npcs_without_sound_configuration": sum(not row["configured"] for row in rows),
        "historical_npcs_with_sound": sum(any(waves) for waves in historical.values()),
        "historical_missing_assets": historical_missing,
        "findings": findings,
        "historical_reference_is_not_runtime_contract": True,
        "periodic_ambient_sounds": "not_configured",
        "client_resources_checked": client is not None,
    }


def configuration(data: Path) -> tuple[dict[int, Any], dict[int, Any]]:
    """Carga el universo de mapas y spawns independientemente del loader de NPC.

    Returns:
        Índice de mapas y configuración íntegra, sin omitir mapas vacíos.
    """
    index = json.loads((data / "world/map_index.json").read_text())
    with (data / "world/map_npcs.toml").open("rb") as file:
        spawns = tomllib.load(file)["map_npcs"]
    return (
        {int(key): value for key, value in index["maps"].items()},
        {int(key): value for key, value in spawns.items()},
    )


def compare_world(
    maps: dict[int, Any],
    spawns: dict[int, Any],
    catalog: NPCCatalog,
    manager: MapManager,
    observed: list[NPC],
) -> dict[str, Any]:
    """Compara expectativas de disco con Redis y con el índice autoritativo.

    Returns:
        Informe por mapa y hallazgos localizados, incluidos faltantes y sobrantes.
    """
    by_map: dict[int, list[NPC]] = defaultdict(list)
    for npc in observed:
        by_map[npc.map_id].append(npc)
    report = []
    findings: list[dict[str, Any]] = []
    for map_id in sorted(maps.keys() | spawns.keys() | by_map.keys()):
        configured = spawns.get(map_id, {})
        present = sorted(by_map[map_id], key=lambda npc: npc.char_index)
        normal = [npc for npc in present if not npc.is_tamed and not npc.summoned_by_user_id]
        expected, local = fixed_spawns(configured, catalog, manager, map_id, normal)
        if map_id not in maps:
            local.append({"code": "unknown_map"})
        loaded = map_id in manager._map_sizes  # ruff: ignore[private-member-access]
        if not loaded:
            local.append({"code": "map_not_loaded"})
        for position, count in Counter((npc.x, npc.y) for npc in normal).items():
            if count > 1:
                local.append({"code": "duplicate_tile", "position": position, "count": count})
        cached = {npc.instance_id: asdict(npc) for npc in manager.get_npcs_in_map(map_id)}
        if cached != {npc.instance_id: asdict(npc) for npc in present}:
            local.append({"code": "redis_map_index_difference"})
        report.append(
            {
                "map_id": map_id,
                "name": maps.get(map_id, {}).get("name", ""),
                "loaded": loaded,
                "has_npc_configuration": bool(
                    configured.get("spawn_points") or configured.get("random_spawns")
                ),
                "expected_fixed": expected,
                "expected_random_areas": configured.get("random_spawns", []),
                "observed": [
                    asdict(npc) | {"roles": roles(catalog.get_npc_data(npc.npc_id) or {})}
                    for npc in present
                ],
                "pets_and_summons": sum(
                    npc.is_tamed or bool(npc.summoned_by_user_id) for npc in present
                ),
                "findings": local,
            }
        )
        findings.extend({"map_id": map_id, **finding} for finding in local)
    return {
        "maps": report,
        "findings": findings,
        "summary": dict(Counter(finding["code"] for finding in findings)),
    }


def point_findings(
    point: dict[str, Any], row: dict[str, Any] | None, manager: MapManager, map_id: int
) -> list[dict[str, Any]]:
    """Comprueba geometría sin confundir la ocupación propia con un muro.

    Returns:
        Problemas del punto que son independientes de que se haya instanciado.
    """
    result = []
    x, y = point["x"], point["y"]
    width, height = manager._map_sizes.get(map_id, (100, 100))  # ruff: ignore[private-member-access]
    blocked = manager._blocked_tiles.get(map_id, set())  # ruff: ignore[private-member-access]
    if row is None:
        result.append({"code": "missing_catalog_npc"})
    if not 1 <= x <= width or not 1 <= y <= height:
        result.append({"code": "out_of_bounds"})
    if (x, y) in blocked:
        result.append({"code": "blocked_spawn"})
    adjacent = [(x + dx, y + dy) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))]
    if not any(
        1 <= px <= width and 1 <= py <= height and (px, py) not in blocked for px, py in adjacent
    ):
        result.append({"code": "no_adjacent_walkable_tile"})
    return result


def fixed_spawns(
    configured: dict[str, Any],
    catalog: NPCCatalog,
    manager: MapManager,
    map_id: int,
    normal: list[NPC],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Empareja multiconjuntos: dos NPC iguales nunca ocultan un faltante.

    Returns:
        Expectativas y discrepancias de todas las instancias fijas del mapa.
    """
    expected: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []
    available: dict[tuple[int, int, int], list[NPC]] = defaultdict(list)
    for npc in normal:
        available[npc.npc_id, npc.x, npc.y].append(npc)
    for ordinal, point in enumerate(configured.get("spawn_points", [])):
        row = catalog.get_npc_data(point["npc_id"])
        entry = {"ordinal": ordinal, **point, "roles": roles(row or {})}
        expected.append(entry)
        findings.extend(
            {**entry, **finding} for finding in point_findings(point, row, manager, map_id)
        )
        matches = available[point["npc_id"], point["x"], point["y"]]
        if not matches:
            findings.append({"code": "missing_fixed_spawn", **entry})
            continue
        actual = matches.pop()
        if not row:
            continue
        fields = {
            "body_id": row.get("body_id", 0),
            "head_id": row.get("head_id", 0),
            "heading": point.get("heading", point.get("direction", 3)),
            "is_hostile": bool(row.get("es_hostil", False)),
            "is_attackable": bool(row.get("es_atacable", True)),
            "is_merchant": bool(row.get("es_mercader", False)),
            "is_banker": bool(row.get("es_banquero", False)),
        }
        findings.extend(
            {
                "code": "runtime_field_mismatch",
                "field": field,
                "expected": value,
                "observed": getattr(actual, field),
                **entry,
            }
            for field, value in fields.items()
            if getattr(actual, field) != value
        )
    for extras in available.values():
        findings.extend(
            {"code": "unexpected_fixed_spawn", "instance_id": npc.instance_id} for npc in extras
        )
    return expected, findings
