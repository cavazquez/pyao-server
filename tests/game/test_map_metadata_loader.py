"""Tests para MapMetadataLoader (metadatos y bloqueados)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.game.coordinate_mask import CoordinateMask
from src.game.map_metadata_loader import MapMetadataLoader


@pytest.fixture
def loader() -> MapMetadataLoader:
    """Instancia configurada del loader para pruebas."""
    return MapMetadataLoader(
        map_ranges=(50, 100, 150, 200, 250),
        max_map_id=290,
        max_coordinate=100,
    )


def test_load_map_with_embedded_blocked(tmp_path: Path, loader: MapMetadataLoader) -> None:
    """Carga usa blocked embebido en metadata."""
    metadata = {
        "w": 120,
        "h": 80,
        "blocked_tiles": [
            {"x": 1, "y": 2, "t": "wall"},
            {"x": 3, "y": 4, "t": "exit", "to_map": 2, "to_x": 5, "to_y": 6},
        ],
    }
    metadata_path = tmp_path / "metadata_001-064.json"
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

    result = loader.load_map_data(1, metadata_path)

    assert result.width == 120
    assert result.height == 80
    assert (1, 2) in result.blocked_tiles
    assert (3, 4) in result.blocked_tiles
    assert result.exit_tiles[1, 3, 4] == {"to_map": 2, "to_x": 5, "to_y": 6}
    assert result.exit_count == 1


def test_load_map_uses_blocked_file_and_transitions(
    tmp_path: Path, loader: MapMetadataLoader
) -> None:
    """Carga usando archivo blocked y transitions externos."""
    # metadata without blocked_tiles -> usa blocked_001-050.json
    metadata_path = tmp_path / "metadata_001-064.json"
    metadata_path.write_text(json.dumps({"w": 100, "h": 90}), encoding="utf-8")

    blocked_path = tmp_path / "blocked_001-050.json"
    blocked_tiles = [
        {"m": 1, "x": 10, "y": 10, "t": "wall"},
        {"m": 2, "x": 1, "y": 1, "t": "wall"},  # debe ignorarse para map_id=1
    ]
    blocked_path.write_text("\n".join(json.dumps(t) for t in blocked_tiles), encoding="utf-8")

    transitions_path = tmp_path / "transitions_001-050.json"
    transitions = {
        "transitions": [
            {
                "from_map": 1,
                "exits": [
                    {"x": 20, "y": 21, "to_map": 3, "to_x": 5, "to_y": 6},
                ],
            }
        ]
    }
    transitions_path.write_text(json.dumps(transitions), encoding="utf-8")

    result = loader.load_map_data(1, metadata_path)

    assert result.width == 100
    assert result.height == 90
    assert (10, 10) in result.blocked_tiles
    assert (1, 1) not in result.blocked_tiles  # de otro mapa
    assert result.exit_tiles[1, 20, 21] == {"to_map": 3, "to_x": 5, "to_y": 6}
    assert result.exit_count == 1


def test_compact_source_cache_does_not_alias_dynamic_flags_or_released_maps(
    tmp_path: Path, loader: MapMetadataLoader
) -> None:
    """Descartar fuentes no borra colisiones/salidas y mutarlas no altera otras cargas."""
    metadata = tmp_path / "metadata_001-050.json"
    metadata.write_text('{"w":100,"h":100}')
    blocked = tmp_path / "blocked_001-050.json"
    blocked.write_text(
        "\n".join(
            json.dumps(row)
            for row in [
                {"m": 1, "x": 1, "y": 1, "t": "wall"},
                {"m": 1, "x": 100, "y": 100, "t": "exit", "to_map": 2, "to_x": 1, "to_y": 1},
                {"m": 2, "x": 2, "y": 2, "t": "wall"},
            ]
        )
    )
    first = loader.load_map_data(1, metadata)
    assert isinstance(first.blocked_tiles, CoordinateMask)
    first.blocked_tiles.discard((1, 1))
    first.exit_tiles.clear()
    again = loader.load_map_data(1, metadata)
    assert (1, 1) in again.blocked_tiles
    assert again.exit_tiles[1, 100, 100] == {"to_map": 2, "to_x": 1, "to_y": 1}
    assert (2, 2) in loader.load_map_data(2, metadata).blocked_tiles
    loader.release_source_cache()
    assert not loader._compact_blocked_cache
    assert not loader._compact_exits
    assert (100, 100) in again.blocked_tiles
    assert again.exit_count == 1
    assert loader.load_map_data(1, metadata).blocked_tiles == again.blocked_tiles
