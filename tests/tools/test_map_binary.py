"""Tests para tools.compression.map_binary."""
# ruff: noqa: D103

import json
from pathlib import Path

import msgpack

from tools.compression.map_binary import convert_json_to_binary


def test_convert_json_to_binary_includes_resources_and_generic_objects(tmp_path: Path) -> None:
    map_data_dir = tmp_path / "map_data"
    map_binary_dir = tmp_path / "map_binary"
    map_data_dir.mkdir()

    blocked_file = map_data_dir / "blocked_1-50.json"
    blocked_file.write_text(
        json.dumps({"m": 1, "t": "b", "x": 10, "y": 20}) + "\n",
        encoding="utf-8",
    )

    objects_file = map_data_dir / "objects_1-50.json"
    objects_file.write_text(
        json.dumps({"m": 1, "t": "anvil", "x": 30, "y": 30}) + "\n"
        + json.dumps({"m": 1, "t": "custom_obj", "x": 40, "y": 40, "g": 99}) + "\n",
        encoding="utf-8",
    )

    assert convert_json_to_binary(map_data_dir, map_binary_dir) is True

    binary_file = map_binary_dir / "maps.msgpack"
    assert binary_file.exists()

    with binary_file.open("rb") as f:
        payload = msgpack.unpack(f, raw=False)

    assert payload["version"] == 1
    assert "1" in payload["blocked"]
    assert [10, 20] in payload["blocked"]["1"]
    assert "1" in payload["anvils"]
    assert [30, 30] in payload["anvils"]["1"]
    assert "1" in payload["objects"]
    assert payload["objects"]["1"][0]["t"] == "custom_obj"
