"""Tests para ndjson_reader."""
# ruff: noqa: D103

import json
from pathlib import Path

from src.services.map.ndjson_reader import iter_ndjson_entries


def test_iter_ndjson_entries_skips_empty_lines(tmp_path: Path) -> None:
    path = tmp_path / "data.json"
    path.write_text("\n\n", encoding="utf-8")

    assert list(iter_ndjson_entries(path)) == []


def test_iter_ndjson_entries_skips_invalid_json(tmp_path: Path) -> None:
    path = tmp_path / "data.json"
    path.write_text(
        "not json\n" + json.dumps({"m": 1, "t": "b", "x": 1, "y": 2}) + "\n", encoding="utf-8"
    )

    entries = list(iter_ndjson_entries(path))

    assert len(entries) == 1
    assert entries[0][1]["m"] == 1


def test_iter_ndjson_entries_yields_valid_entries(tmp_path: Path) -> None:
    path = tmp_path / "data.json"
    path.write_text(
        json.dumps({"m": 1, "t": "tree", "x": 10, "y": 20}) + "\n",
        encoding="utf-8",
    )

    entries = list(iter_ndjson_entries(path))

    assert len(entries) == 1
    line_number, entry = entries[0]
    assert line_number == 1
    assert entry == {"m": 1, "t": "tree", "x": 10, "y": 20}
