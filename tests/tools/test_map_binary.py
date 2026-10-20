"""El CLI prepara exactamente el formato de caché que consume el servidor."""

import json
import os
import subprocess
import sys
from pathlib import Path

from src.game.coordinate_mask import MASK_BYTES
from src.services.map.binary_cache import COMPACT_CACHE_NAME, MapBinaryCache
from tools.compression.map_binary import check_binary_needs_rebuild, convert_json_to_binary


def sources(directory: Path) -> tuple[Path, Path]:
    """Prepara recursos y datos que deben permanecer íntegros en las fuentes.

    Returns:
        Directorios de fuente y destino separados.
    """
    source, cache = directory / "sources", directory / "cache"
    source.mkdir()
    (source / "blocked_1-50.json").write_text('{"m":1,"t":"b","x":10,"y":20}\n')
    (source / "objects_1-50.json").write_text(
        '{"m":1,"t":"anvil","x":30,"y":30}\n{"m":1,"t":"custom_obj","x":40,"y":40,"g":99}\n'
    )
    (source / "transitions_1-50.json").write_text('{"from_map":1,"exits":[]}\n')
    return source, cache


def test_converter_output_loads_in_runtime_and_preserves_complete_sources(tmp_path):
    """Una conversión se carga sin reconvertir y no sustituye el catálogo fuente."""
    source, destination = sources(tmp_path)
    original = {path.name: path.read_bytes() for path in source.iterdir()}
    assert convert_json_to_binary(source, destination)
    assert (destination / COMPACT_CACHE_NAME).is_file()
    assert not (destination / "maps.msgpack").exists()
    assert not (destination / "metadata.json").exists()
    resources = {}
    reader = MapBinaryCache(source, resources, {}, {}, cache_dir=destination)
    assert reader.try_load_from_binary()
    assert (10, 20) in resources["map_1"]["blocked"]
    assert (30, 30) in resources["map_1"]["anvils"]
    assert len(resources["map_1"]["blocked"].to_bytes()) == MASK_BYTES
    assert {path.name: path.read_bytes() for path in source.iterdir()} == original
    assert not check_binary_needs_rebuild(source, destination)
    path = source / "blocked_1-50.json"
    previous = path.stat()
    path.write_text(path.read_text().replace('"x":10', '"x":11'))
    os.utime(path, ns=(previous.st_atime_ns, previous.st_mtime_ns))
    assert check_binary_needs_rebuild(source, destination)


def test_cli_status_detects_corruption_and_leaves_legacy_files_untouched(tmp_path):
    """Convert/status usan rutas explícitas y no eliminan archivos viejos ajenos."""
    source, destination = sources(tmp_path)
    destination.mkdir()
    legacy = destination / "maps.msgpack"
    legacy.write_bytes(b"previous operator cache")
    command = [
        sys.executable,
        "-m",
        "tools.compression.map_binary",
        "--map-data",
        str(source),
        "--map-binary",
        str(destination),
    ]
    assert subprocess.run([*command, "status"], capture_output=True, timeout=15).returncode == 1
    assert subprocess.run([*command, "convert"], capture_output=True, timeout=15).returncode == 0
    assert subprocess.run([*command, "status"], capture_output=True, timeout=15).returncode == 0
    assert legacy.read_bytes() == b"previous operator cache"
    (destination / COMPACT_CACHE_NAME).write_bytes(b"truncated")
    assert subprocess.run([*command, "status"], capture_output=True, timeout=15).returncode == 1
