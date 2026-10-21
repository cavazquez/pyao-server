"""Regresiones del inventario completo de mapas y combinaciones dirigidas."""
# ruff: noqa: INP001

import json
import sys
from collections.abc import Sequence
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.command_handlers.walk_movement_handler import WalkMovementHandler
from src.game.map_manager import MapManager
from src.runtime_paths import maps_dir
from tools.analysis import audit_world_routes as audit


def dataset(root: Path, routes: Sequence[Sequence[int]] | None = None) -> Path:
    """Crea tres mapas y sus datos completos sin Redis."""
    if routes is None:
        routes = [(1, 1, 100, 2, 100, 1), (2, 20, 20, 3, 30, 30)]
    root.mkdir(parents=True, exist_ok=True)
    (root / "metadata_001-050.json").write_text(
        "\n".join(json.dumps({"i": m, "w": 100, "h": 100}) for m in (1, 2, 3)) + "\n"
    )
    grouped: dict[int, list[dict[str, int]]] = {}
    for m, x, y, n, a, b in routes:
        grouped.setdefault(m, []).append({"x": x, "y": y, "to_map": n, "to_x": a, "to_y": b})
    (root / "transitions_001-050.json").write_text(
        "\n".join(json.dumps({"from_map": m, "exits": e}) for m, e in grouped.items()) + "\n"
    )
    for prefix in ("blocked", "objects"):
        (root / f"{prefix}_001-050.json").write_text("")
    return root


def test_matrix_checks_all_ordered_pairs_and_shortest_paths(tmp_path: Path) -> None:
    """Incluye pares sin camino y caminos indirectos sin inventar retornos."""
    root = dataset(tmp_path)
    report, exits, matrix = audit.inspect_world(root)
    assert report["summary"]["maps"] == 3
    assert report["summary"]["exit_tiles"] == 2
    assert report["summary"]["all_ordered_map_pairs"] == 9
    assert len(exits) == 2
    assert (
        next(row for row in matrix if row["from_map"] == 1 and row["to_map"] == 3)["graph_hops"]
        == 2
    )
    unreachable = next(row for row in matrix if row["from_map"] == 3 and row["to_map"] == 1)
    assert not unreachable["graph_hops"]
    assert not report["findings"].get("invalid_reference_or_coordinate")
    assert report["summary"]["maps_without_exits"] == [3]
    assert report["summary"]["maps_without_entries"] == [1]
    assert len(report["findings"]["no_direct_reverse_pair"]) == 2


@pytest.mark.parametrize(("field", "value"), [(1, 0), (2, 101), (3, 4), (4, 0), (5, 101)])
def test_invalid_coordinates_and_maps_are_reported(tmp_path: Path, field: int, value: int) -> None:
    """Rechaza 0/101 y referencias a mapas inexistentes."""
    route = [1, 50, 50, 2, 50, 50]
    route[field] = value
    report, _, _ = audit.inspect_world(dataset(tmp_path, [route]))
    assert len(report["findings"]["invalid_reference_or_coordinate"]) == 1


def test_duplicate_source_is_never_silently_overwritten(tmp_path: Path) -> None:
    """Dos destinos para una casilla quedan como error del inventario."""
    report, _, _ = audit.inspect_world(
        dataset(tmp_path, [(1, 20, 20, 2, 30, 30), (1, 20, 20, 3, 40, 40)])
    )
    assert report["summary"]["duplicate_sources"] == [[1, 20, 20]]
    assert report["summary"]["exit_tiles"] == 2


def test_water_solid_destinations_and_chained_portals_are_distinct(tmp_path: Path) -> None:
    """El agua no se presenta como una pared y una cadena no inventa retorno."""
    root = dataset(tmp_path, [(1, 20, 20, 2, 30, 30), (2, 30, 30, 1, 20, 20)])
    (root / "blocked_001-050.json").write_text(
        json.dumps({"m": 1, "x": 20, "y": 20, "t": "b"}) + "\n"
    )
    (root / "objects_001-050.json").write_text(
        json.dumps({"m": 2, "x": 30, "y": 30, "t": "water"}) + "\n"
    )
    report, _, _ = audit.inspect_world(root)
    assert report["findings"]["solid_destination"] == [[2, 30, 30, 1, 20, 20]]
    assert report["findings"]["source_requires_portal_override"] == [[1, 20, 20, 2, 30, 30]]
    assert len(report["findings"]["water_land_mismatch"]) == 2
    assert len(report["findings"]["landing_on_another_exit"]) == 2
    assert "no_direct_reverse_pair" not in report["findings"]


def test_bad_ndjson_and_missing_inputs_are_errors(tmp_path: Path) -> None:
    """Una entrada ilegible no desaparece del alcance auditado."""
    root = dataset(tmp_path)
    (root / "metadata_001-050.json").write_text("[]\n")
    with pytest.raises(ValueError, match="se esperaba"):
        audit.inspect_world(root)
    (root / "metadata_001-050.json").unlink()
    with pytest.raises(ValueError, match="Faltan"):
        audit.inspect_world(root)


@pytest.mark.parametrize("value", [True, 1.5, "1", None])
def test_boolean_float_and_string_are_not_valid_coordinates(value: object) -> None:
    """No convierte silenciosamente valores que no representan enteros."""
    with pytest.raises(ValueError, match="inválido"):
        audit.integer({"x": value}, "x")


def test_duplicate_metadata_is_an_error(tmp_path: Path) -> None:
    """Un mapa duplicado no puede reemplazar el registro anterior."""
    root = dataset(tmp_path)
    with (root / "metadata_001-050.json").open("a") as f:
        f.write(json.dumps({"i": 1, "w": 100, "h": 100}) + "\n")
    with pytest.raises(ValueError, match="repetido"):
        audit.inspect_world(root)


def test_cli_is_read_only_and_rejects_stale_inventory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Regenerar evidencia no modifica entradas y detecta un reporte obsoleto."""
    root = dataset(tmp_path / "input")
    output = tmp_path / "proof"
    before = {p.name: p.read_bytes() for p in root.iterdir()}
    monkeypatch.setattr(sys, "argv", ["audit", "--source", str(root), "--output", str(output)])
    assert audit.main() == 0
    report = output / "audit.json"
    monkeypatch.setattr(sys, "argv", ["audit", "--source", str(root), "--check", str(report)])
    assert audit.main() == 0
    assert len((output / "map-pair-matrix.csv").read_text().splitlines()) == 10
    assert len((output / "exits.jsonl").read_text().splitlines()) == 2
    assert before == {p.name: p.read_bytes() for p in root.iterdir()}
    changed = json.loads(report.read_text())
    changed["summary"]["maps"] = 99
    report.write_text(json.dumps(changed))
    assert audit.main() == 1
    capsys.readouterr()


def test_cli_rejects_duplicate_sources(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Los duplicados hacen fallar el comando incluso sin comparar un reporte."""
    root = dataset(tmp_path, [(1, 20, 20, 2, 30, 30), (1, 20, 20, 3, 40, 40)])
    monkeypatch.setattr(sys, "argv", ["audit", "--source", str(root)])
    assert audit.main() == 1
    capsys.readouterr()


@pytest.fixture(scope="module")
def versioned_world() -> tuple[dict, list[dict], list[dict]]:
    """Audita una sola vez el conjunto versionado completo de 290 mapas."""
    from tools.analysis.world_roles import review_roles
    from tools.analysis.water_routes import classify
    import hashlib

    report, exits, matrix = audit.inspect_world(maps_dir())
    report["roles"] = review_roles(maps_dir(), Path("data/world/map_roles.json"))
    path = Path("data/world/water_routes.json")
    assert json.loads(path.read_text()) == classify(exits)
    report["water_policy"] = {
        "candidates": len(classify(exits)["routes"]),
        "manifest_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }
    return report, exits, matrix


def test_versioned_inventory_is_current(
    versioned_world: tuple[dict, list[dict], list[dict]],
) -> None:
    """Un cambio de cualquier archivo o enlace exige revisar el inventario."""
    report, exits, matrix = versioned_world
    snapshot = Path(__file__).resolve().parents[2] / "docs/catalogs/world-routes.json"
    assert report == json.loads(snapshot.read_text())
    assert report["summary"]["maps"] == 290
    assert len(exits) == 59855
    assert len(matrix) == 84100
    assert not report["findings"].get("invalid_reference_or_coordinate")
    assert not report["summary"]["duplicate_sources"]


@pytest.mark.asyncio
async def test_every_exit_and_heading_matches_real_movement_calculation(
    versioned_world: tuple[dict, list[dict], list[dict]],
) -> None:
    """Comprueba las 239.672 entradas cardinales con el handler real sin Redis."""
    report, exits, _ = versioned_world
    maps = MapManager()
    maps._map_sizes = {
        int(identity): (row["metadata"]["w"], row["metadata"]["h"])
        for identity, row in report["maps"].items()
    }
    maps._exit_tiles.update(
        {
            (row["from_map"], row["x"], row["y"]): {
                "to_map": row["to_map"],
                "to_x": row["to_x"],
                "to_y": row["to_y"],
            }
            for row in exits
        }
    )
    handler = WalkMovementHandler(None, maps, None, None, None, None, MagicMock())
    checked = 0
    for row in exits:
        width, height = maps.get_map_size(row["from_map"])
        for heading, dx, dy in audit.DIRECTIONS:
            x, y = row["x"] - dx, row["y"] - dy
            if not 1 <= x <= width or not 1 <= y <= height:
                continue
            actual = await handler._calculate_new_position(heading, x, y, row["from_map"])
            assert actual == (row["to_x"], row["to_y"], row["to_map"], True)
            checked += 1
    assert checked == report["summary"]["cardinal_inputs"] == 239420
