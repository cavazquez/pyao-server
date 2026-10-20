"""La caché compacta es descartable, atómica y está ligada a su fuente real."""

from src.game.coordinate_mask import TERRAIN_LAYERS, CoordinateMask
from src.services.map import binary_cache
from src.services.map.binary_cache import COMPACT_CACHE_NAME, MapBinaryCache


def test_compact_cache_preserves_flags_and_rejects_changed_source(tmp_path, monkeypatch) -> None:
    """Cambiar contenido aun con igual longitud/mtime invalida los planos cacheados."""
    source = tmp_path / "sources"
    source.mkdir()
    data = source / "blocked_001-050.json"
    data.write_text('{"m":1,"x":1,"y":1,"t":"b"}\n')
    monkeypatch.setattr(binary_cache, "MAP_BINARY_DIR", tmp_path / "cache")
    resources = {"map_1": {layer: CoordinateMask({(1, 1), (100, 100)}) for layer in TERRAIN_LAYERS}}
    signs, doors = {"map_1": {(5, 5): 123}}, {"map_1": {(6, 6): 456}}
    cache = MapBinaryCache(source, resources, signs, doors)
    assert cache.generate_binary_cache()
    assert (tmp_path / "cache" / COMPACT_CACHE_NAME).stat().st_size < 10000
    loaded, loaded_signs, loaded_doors = {}, {}, {}
    reader = MapBinaryCache(source, loaded, loaded_signs, loaded_doors)
    assert reader.try_load_from_binary()
    assert loaded == resources
    assert loaded_signs == signs
    assert loaded_doors == doors
    loaded["map_1"]["blocked"].discard((1, 1))
    assert (1, 1) in resources["map_1"]["blocked"]
    data.write_text(data.read_text().replace('"x":1', '"x":2'))
    assert not reader.try_load_from_binary()


def test_partial_or_foreign_cache_never_populates_a_fixture(tmp_path, monkeypatch) -> None:
    """Un archivo parcial y otro directorio con nombres iguales se reconstruyen."""
    monkeypatch.setattr(binary_cache, "MAP_BINARY_DIR", tmp_path)
    path = tmp_path / COMPACT_CACHE_NAME
    path.write_bytes(b"not a msgpack cache")
    resources = {}
    assert not MapBinaryCache(tmp_path / "a", resources, {}, {}).try_load_from_binary()
    assert resources == {}
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir()
    b.mkdir()
    for directory in (a, b):
        (directory / "blocked_001-050.json").write_text('{"m":1}\n')
    values = {"map_1": {layer: CoordinateMask() for layer in TERRAIN_LAYERS}}
    assert MapBinaryCache(a, values, {}, {}).generate_binary_cache()
    assert not MapBinaryCache(b, resources, {}, {}).try_load_from_binary()
