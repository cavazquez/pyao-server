"""Mide las estructuras reales de todos los mapas con caché propia y fuentes fijadas.

Ejecutar en un checkout de referencia y en el modificado, con PYAO_STATE_DIR vacío
para medir carga fría, y repetir con el mismo directorio para carga caliente.
PYAO_MAPS_DIR debe apuntar al mismo catálogo en ambas ejecuciones.
"""

import argparse
import gc
import hashlib
import json
import resource
import statistics
import sys
import time
from pathlib import Path

from src.core.server_initializer import ServerInitializer
from src.game.map_manager import MapManager
from src.runtime_paths import maps_dir
from src.services.map.map_resources_service import MapResourcesService


def owned_bytes(value, seen=None):
    if seen is None:
        seen = set()
    if id(value) in seen:
        return 0
    seen.add(id(value))
    size = sys.getsizeof(value)
    if isinstance(value, dict):
        return size + sum(owned_bytes(k, seen) + owned_bytes(v, seen) for k, v in value.items())
    if isinstance(value, (list, tuple, set, frozenset)):
        return size + sum(owned_bytes(v, seen) for v in value)
    if hasattr(value, "__dict__"):
        return size + owned_bytes(vars(value), seen)
    return size


def digest_layers(resources):
    rows = {}
    for key, values in sorted(resources.items()):
        rows[key] = {}
        for layer in ("blocked", "water", "trees", "mines", "anvils", "forges"):
            coords = sorted(values[layer])
            rows[key][layer] = {"count": len(coords), "sha256": hashlib.sha256(json.dumps(coords).encode()).hexdigest()}
    return rows


def run():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    resources = MapResourcesService()
    resources_seconds = time.perf_counter() - started
    manager = MapManager()
    started = time.perf_counter()
    ServerInitializer._load_map_tiles(manager)
    collision_seconds = time.perf_counter() - started
    gc.collect()
    retained_rss = next(int(line.split()[1]) for line in Path("/proc/self/status").read_text().splitlines() if line.startswith("VmRSS:"))
    # Reportar memoria antes de los diccionarios temporales de huellas/equivalencia.
    sizes = {"resources": owned_bytes(resources.resources), "map_manager": owned_bytes(manager)}
    points = [(mid, x, y) for mid in (1, 28, 91, 143, 290) for x in range(1, 101, 3) for y in range(1, 101, 3)]
    timings = []
    matches = 0
    for _ in range(21):
        started = time.perf_counter_ns()
        matches = sum(resources.is_blocked(mid, x, y) for mid, x, y in points)
        timings.append((time.perf_counter_ns() - started) / len(points) / 1000)
    timings.sort()
    collision = {str(mid): sorted(layer) for mid, layer in sorted(manager._blocked_tiles.items())}
    exits = sorted(manager._exit_tiles.items())
    files = sorted(maps_dir().glob("*.json"))
    report = {"python": sys.version, "sources": {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in files}, "resources_load_seconds": resources_seconds, "collision_load_seconds": collision_seconds, "owned_bytes": sizes, "retained_rss_kib": retained_rss, "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, "queries": {"p50_us": statistics.median(timings), "p95_us": timings[19], "p99_us": timings[20], "matches": matches}, "layers": digest_layers(resources.resources), "collision_sha256": hashlib.sha256(json.dumps(collision, sort_keys=True).encode()).hexdigest(), "exits_sha256": hashlib.sha256(json.dumps(exits, sort_keys=True).encode()).hexdigest(), "limitations": ["Linux process RSS after GC; peak includes imports and hash preparation", "Microbenchmark of point queries, not whole-server RTT", "Use identical input hashes before comparing results"]}
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: report[k] for k in ("resources_load_seconds", "collision_load_seconds", "owned_bytes", "retained_rss_kib", "queries")}))


if __name__ == "__main__":
    run()
