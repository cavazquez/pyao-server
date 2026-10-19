"""Pesca por ubicación: litoral, islas, mapas continuos y agua interior."""

import itertools
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.services.fishing_zones import FishingZones
from src.services.gathering import gather


@pytest.fixture
def sea(tmp_path, monkeypatch):
    """Prepara un mar continuo, una isla y un lago aislado."""
    data = tmp_path / "data"
    (data / "world").mkdir(parents=True)
    (data / "world/map_metadata.toml").write_text(
        '[map_1]\ntype="water"\n[map_2]\ntype="water"\n[map_3]\ntype="wilderness"\n'
    )
    rules = data / "fishing.toml"
    rules.write_bytes((Path(__file__).parents[2] / "data/fishing.toml").read_bytes())
    (tmp_path / "transitions_test.json").write_text(
        json.dumps(
            {"from_map": 1, "exits": [{"x": 100, "y": 50, "to_map": 2, "to_x": 1, "to_y": 50}]}
        )
        + "\n"
    )

    def water(m, x, y):
        return (
            1 <= x <= 100
            and 1 <= y <= 100
            and (
                (m == 1 and x >= 4 and (x, y) != (50, 50))
                or m == 2
                or (m == 3 and 10 <= x <= 50 and 10 <= y <= 50)
            )
        )

    terrain = SimpleNamespace(has_water=water, maps_dir=tmp_path)
    monkeypatch.setattr("src.services.fishing_zones.data_dir", lambda: data)
    return FishingZones(terrain, rules)


def test_island_is_a_real_coast_and_distance_is_cached(sea):
    """Una isla acorta la distancia y las consultas siguientes reutilizan su clasificación."""
    assert sea.classify((1, 49, 50)) == ("costa", 0)
    assert sea.classify((1, 44, 50)) == ("mar intermedio", 5)
    assert sea.classify((1, 25, 50))[0] == "mar adentro"
    sea.terrain.has_water = lambda *_: (_ for _ in ()).throw(
        AssertionError("La caché consultó nuevamente el terreno")
    )
    assert sea.classify((1, 44, 50)) == ("mar intermedio", 5)


def test_connected_map_edge_does_not_become_a_fake_shore(sea):
    """El borde conectado conserva la distancia al litoral del mapa vecino."""
    band, distance = sea.classify((2, 2, 50))
    assert band == "mar adentro"
    assert distance > 12


def test_inland_water_never_awards_open_sea_species(sea):
    """Un lago interior entrega únicamente pescado común."""
    assert sea.classify((3, 30, 30))[0] == "costa"
    assert {sea.catch((3, 30, 30))[0] for _ in range(20)} == {139}


def test_distributions_have_increasing_expected_catalog_value(sea):
    """El valor esperado crece y el pez dorado queda reservado al mar adentro."""
    prices = {139: 8, 544: 16, 545: 13, 546: 13}
    values = [
        sum(prices[i] * w for i, w in zip(b["items"], b["weights"], strict=True))
        / sum(b["weights"])
        for b in sea.bands
    ]
    assert all(a < b for a, b in itertools.pairwise(values))
    assert 544 not in sea.bands[0]["items"]
    assert 544 not in sea.bands[1]["items"]


@pytest.mark.asyncio
async def test_remote_target_rejects_before_species_selection(mechanics_world):
    """Un objetivo remoto no selecciona especie ni altera inventario."""
    w = mechanics_world
    w.terrain.has_water = lambda *_: True
    result = await gather(w.player, w.inventory, w.terrain, 1, 12, 2, 90, 90)
    assert result["applied"] is False
    assert await w.redis.hgetall("player:1:inventory") == {}
