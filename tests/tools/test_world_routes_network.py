"""La unión exige cobertura completa y procedencia común de los controles TCP."""
# ruff: noqa: INP001

import hashlib
import json
import shutil
import subprocess  # ruff: ignore[suspicious-subprocess-import] -- consulta Git local de sólo lectura
from pathlib import Path

import pytest

from tools.analysis import audit_world_routes_network as network


def partitions(root: Path) -> list[Path]:
    """Crea recibos sintéticos para probar el validador, sin atribuirles tráfico real.

    Returns:
        Dos archivos de una matriz mínima de ocho entradas y dos pares.
    """
    source = Path(network.__file__).resolve()
    executable = shutil.which("git")
    assert executable is not None
    commit = subprocess.check_output(  # ruff: ignore[subprocess-without-shell-equals-true] -- comando Git fijo
        [executable, "rev-parse", "HEAD"], cwd=source.parents[2], text=True
    ).strip()
    labels = (
        "player",
        "npc-friendly",
        "npc-hostile",
        "reservation",
        "door",
        "no-boat",
        "insufficient-navigation",
        "dead",
        "missing-map",
        "x-zero",
        "x-over",
        "y-zero",
        "y-over",
    )
    paths = []
    for index in range(2):
        directory = root / str(index)
        directory.mkdir()
        path = directory / "result.json"
        path.write_text(
            json.dumps(
                {
                    "passed": True,
                    "partial": False,
                    "dirty": False,
                    "server_commit": commit,
                    "runtime_source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                    "source_hashes": {"synthetic": "fixture"},
                    "inventory_summary": {
                        "cardinal_inputs": 8,
                        "exit_tiles": 2,
                        "directed_pairs": 2,
                    },
                    "shard": index,
                    "shards": 2,
                    "exit_tiles_selected": 1,
                    "directed_pairs_selected": [[index + 1, index + 2]],
                    "counts": {"all-exit-directions": 4, "total": 17, **dict.fromkeys(labels, 1)},
                }
            )
        )
        paths.append(path)
    return paths


def test_complete_partition_union_counts_every_case_once(tmp_path: Path) -> None:
    """Una unión válida conserva hashes y suma cardinales y controles adversos."""
    paths = partitions(tmp_path)
    result = network.combine(paths, tmp_path)
    assert result["full_coverage"]
    assert result["counts"]["total"] == 34
    assert result["counts"]["all-exit-directions"] == 8
    assert len(result["evidence_sha256"]) == 2


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("partial", True, "completas"),
        ("dirty", True, "limpias"),
        ("shard", 0, "repetidas"),
        ("server_commit", "other", "otro código"),
        ("directed_pairs_selected", [[1, 2]], "no cubre"),
        ("counts", {"all-exit-directions": 4, "total": 4}, "Faltan controles"),
    ],
)
def test_partial_duplicate_stale_or_missing_controls_never_pass(
    tmp_path: Path, field: str, value: object, message: str
) -> None:
    """Una muestra parcial o de otra fuente no acredita la auditoría completa."""
    paths = partitions(tmp_path)
    record = json.loads(paths[1].read_text())
    record[field] = value
    paths[1].write_text(json.dumps(record))
    with pytest.raises(ValueError, match=message):
        network.combine(paths, tmp_path)
    assert not (tmp_path / "result.json").exists()


def test_missing_partition_is_rejected(tmp_path: Path) -> None:
    """Un job correcto no puede reemplazar la partición que falta."""
    paths = partitions(tmp_path)
    with pytest.raises(ValueError, match="Faltan particiones"):
        network.combine(paths[:1], tmp_path)
