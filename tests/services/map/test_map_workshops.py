"""Talleres reales, validación del catálogo y publicación al entrar al mapa."""

import struct
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.runtime_paths import data_dir
from src.services.map.map_workshops import load_workshops
from src.services.map.player_map_service import PlayerMapService
from tools.extraction.extract_map_workshops import read_workshops


def test_workshops_restore_inf_objects_over_legacy_cached_maps():
    """El catálogo repara cachés sin talleres, conservando los recursos anteriores."""
    terrain = {f"map_{i}": {"blocked": {(99, 99)}} for i in range(1, 291)}
    workshops = load_workshops(data_dir() / "world/map_workshops.toml", terrain)
    assert sum(map(len, workshops.values())) == 20
    assert (36, 62) in terrain["map_1"]["anvils"]
    assert (32, 62) in terrain["map_1"]["forges"]
    assert {(99, 99), (36, 62), (32, 62)} <= terrain["map_1"]["blocked"]
    assert (36, 62, 600) in workshops[1]


@pytest.mark.parametrize("value", ["x = true", "x = 0", "x = 101", 'kind = "tree"'])
def test_invalid_workshop_rejected(tmp_path: Path, value: str):
    """Datos corruptos no habilitan fabricar ni bloquear tiles arbitrarios."""
    row = {"map_id": "1", "x": "20", "y": "20", "grh_index": "600", "kind": '"anvil"'}
    key, val = value.split(" = ")
    row[key] = val
    path = tmp_path / "workshops.toml"
    path.write_text("[[workshop]]\n" + "\n".join(f"{k} = {v}" for k, v in row.items()))
    with pytest.raises(ValueError, match="Taller inválido"):
        load_workshops(path, {"map_1": {"blocked": set()}})


def test_extractor_reads_inf_flags_and_object_ids(tmp_path: Path):
    """Un NPC y un exit anteriores al yunque no desplazan las coordenadas."""
    path = tmp_path / "Mapa1.inf"
    path.write_bytes(
        bytes(10)
        + bytes([7])
        + struct.pack("<HHHHHH", 2, 3, 4, 99, 169, 1)
        + bytes([4])
        + struct.pack("<HH", 385, 1)
        + bytes(9998)
    )
    rows = read_workshops(path, {169: ("anvil", 600), 385: ("forge", 722)})
    assert [(r["x"], r["y"], r["kind"]) for r in rows] == [(1, 1, "anvil"), (2, 1, "forge")]


@pytest.mark.asyncio
async def test_map_entry_sends_workshop_graphic_and_block():
    """El taller visible y la validación de terreno comparten el mismo catálogo."""
    maps = SimpleNamespace(send_ground_items_snapshot=AsyncMock(return_value=0))
    player_map_service = PlayerMapService(
        AsyncMock(),
        AsyncMock(),
        maps,
        AsyncMock(),
        map_resources=SimpleNamespace(workshops={1: [(36, 62, 600)]}),
    )
    sender = SimpleNamespace(send_object_create=AsyncMock(), send_block_position=AsyncMock())
    assert await player_map_service._send_ground_items_in_map(1, sender) == 1
    sender.send_object_create.assert_awaited_once_with(36, 62, 600)
    sender.send_block_position.assert_awaited_once_with(36, 62, blocked=True)
