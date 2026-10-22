"""Compare CPython modes using actual PyAO kernels, without changing a live game.

python -m tools.analysis.interpreter_study --output docs/benchmarks/interpreter.json
The probe runs in independent processes. Full network latency is measured with
tools.benchmark and tools.profile_runtime; these kernel timings do not replace it.
"""

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import sysconfig
import time

ROOT = Path(__file__).resolve().parents[2]


def percentile(values, fraction):
    ordered = sorted(values)
    return ordered[max(0, min(len(ordered) - 1, math.ceil(fraction * len(ordered)) - 1))]


def runtime_metadata():
    jit = getattr(sys, "_jit", None)
    names = (
        "CONFIG_ARGS",
        "PY_CFLAGS",
        "PY_CFLAGS_NODIST",
        "PY_LDFLAGS_NODIST",
        "CC",
        "Py_GIL_DISABLED",
        "PGO_PROF_USE_FLAG",
        "LLVM_PROF_MERGER",
        "HOST_GNU_TYPE",
        "SOABI",
    )
    return {
        "executable": sys.executable,
        "version": sys.version,
        "implementation": platform.python_implementation(),
        "machine": platform.machine(),
        "platform": platform.platform(),
        "processor": platform.processor(),
        "cpu_count": os.cpu_count(),
        "affinity": sorted(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else None,
        "optimize": sys.flags.optimize,
        "build": {name: sysconfig.get_config_var(name) for name in names},
        "jit_available": bool(jit and jit.is_available()),
        "jit_enabled": bool(jit and jit.is_enabled()),
        "gil_enabled": getattr(sys, "_is_gil_enabled", lambda: True)(),
    }


def measure(function, samples, batch):
    checksum = 0
    for index in range(1000):
        checksum += int(function(index))
    wall, cpu = [], []
    for sample in range(samples):
        started, process = time.perf_counter_ns(), time.process_time_ns()
        for index in range(batch):
            checksum += int(function(sample * batch + index))
        cpu.append((time.process_time_ns() - process) / batch)
        wall.append((time.perf_counter_ns() - started) / batch)
    return {
        "samples": samples,
        "operations_per_sample": batch,
        "wall_ns": {
            "p50": percentile(wall, 0.5),
            "p95": percentile(wall, 0.95),
            "p99": percentile(wall, 0.99),
            "mean": statistics.mean(wall),
            "stdev": statistics.stdev(wall),
        },
        "cpu_ns_mean": statistics.mean(cpu),
        "operations_per_second": 1e9 / statistics.mean(wall),
        "checksum": checksum,
    }


def probe(samples, batch):
    started, cpu = time.perf_counter(), time.process_time()
    from src.game.coordinate_mask import CoordinateMask
    from src.game.map_manager import MapManager
    from src.models.npc import NPC
    from src.network.msg_character import build_character_move_response
    from src.services.combat.physical_plan import backstab_chance
    from src.utils.ground_state import GroundState, stack_identity

    imports = {
        "wall_seconds": time.perf_counter() - started,
        "cpu_seconds": time.process_time() - cpu,
    }
    maps = MapManager()
    sender = object()  # Only an identity for the in-memory index, never used as transport.
    for user in range(1, 1025):
        maps.add_player(1 + user % 8, user, sender, f"Benchmark{user}")
    for number in range(256):
        maps.add_npc(
            2,
            NPC(
                1,
                10001 + number,
                f"probe-{number}",
                2,
                1 + number % 100,
                1 + number // 100,
                3,
                "Probe",
                "",
                1,
                0,
                100,
                100,
                1,
                True,
                True,
            ),
        )
    mask = CoordinateMask((x, y) for x in range(1, 101) for y in range(1, 101) if (x + y) % 3)
    ground = GroundState(2, None)
    for tile in range(30):
        ground.append(
            1 + tile,
            50,
            {
                "item_id": 2,
                "quantity": 1,
                "stack_id": stack_identity(f"probe-{tile}"),
                "grh_index": 500,
            },
        )
    serialized = ground.encode()
    cases = {
        "map_membership": lambda i: mask.contains_xy(1 + i % 100, 1 + (i // 100) % 100),
        "movement_collision": lambda i: maps.can_move_to(2, 1 + i % 100, 50),
        "player_name_1024": lambda i: maps.find_player_by_username(f"benchmark{1 + i % 1024}") or 0,
        "npc_index_256": lambda i: maps.get_npc_by_char_index(2, 10001 + i % 256).char_index,
        "combat_backstab": lambda i: backstab_chance(i % 101, 1 + i % 12),
        "packet_serialization": lambda i: len(build_character_move_response(1, 1 + i % 100, 50)),
        "ground_decode_30": lambda _i: len(GroundState(2, serialized).positions()),
    }
    measured = {
        name: measure(function, samples, max(10, batch // 20) if "ground" in name else batch)
        for name, function in cases.items()
    }
    try:
        import resource

        maximum = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        rss = maximum if sys.platform == "darwin" else maximum * 1024
    except ImportError:
        rss = None
    return {
        "runtime": runtime_metadata(),
        "imports": imports,
        "kernels": measured,
        "peak_rss_bytes": rss,
        "fixture": {
            "players": 1024,
            "maps": 8,
            "npcs": 256,
            "ground_stacks": 30,
            "seed": "deterministic-v1",
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--probe", action="store_true")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--samples", type=int, default=101)
    parser.add_argument("--batch", type=int, default=1000)
    parser.add_argument(
        "--include-jit", action="store_true", help="Compare JIT only on a build that provides it"
    )
    args = parser.parse_args()
    if (
        not 2 <= args.samples <= 1000
        or not 10 <= args.batch <= 10000
        or not 1 <= args.repeats <= 20
    ):
        parser.error("samples=2..1000, batch=10..10000, repeats=1..20")
    if args.probe:
        print(json.dumps(probe(args.samples, args.batch)))
        return
    if args.output is None:
        parser.error("--output is required")
    rows = []
    # Rotate order to reduce bias from thermal drift, with the same deterministic fixture.
    variants = [("default", [], {}), ("-O", ["-O"], {}), ("-OO", ["-OO"], {})]
    if args.include_jit:
        available = subprocess.check_output(
            [
                args.python,
                "-c",
                "import sys; print(int(bool(getattr(sys, '_jit', None) and sys._jit.is_available())))",
            ],
            text=True,
        ).strip()
        if available != "1":
            parser.error("--include-jit requires a runtime with sys._jit.is_available()")
        variants.append(("jit-on", [], {"PYTHON_JIT": "1"}))
    for repeat in range(args.repeats):
        offset = repeat % len(variants)
        for name, flags, overrides in variants[offset:] + variants[:offset]:
            command = [
                args.python,
                *flags,
                "-m",
                "tools.analysis.interpreter_study",
                "--probe",
                "--samples",
                str(args.samples),
                "--batch",
                str(args.batch),
            ]
            started = time.perf_counter()
            result = subprocess.run(
                command,
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
                timeout=180,
                env={
                    **{
                        key: value
                        for key, value in os.environ.items()
                        if key not in {"PYTHONOPTIMIZE", "PYTHON_JIT"}
                    },
                    **overrides,
                },
            )
            rows.append(
                {
                    "mode": name,
                    "repeat": repeat,
                    "command": command,
                    "process_wall_seconds": time.perf_counter() - started,
                    **json.loads(result.stdout),
                }
            )
    hashes = {
        str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in ROOT.glob("src/**/*.py")
    }
    report = {
        "schema": 1,
        "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "source_hashes": hashes,
        "probe_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "rows": rows,
        "limitations": [
            "fresh process, warm filesystem cache; OS caches are not flushed",
            "kernel throughput is not simultaneous-player capacity",
            "no Redis, network, disk or Argon2 waits are included in kernels",
            "PGO/LTO are measured as built; no interpreter rebuild is implied",
            "JIT is recorded as available/enabled; unsupported builds are not treated as JIT measurements",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(f"Saved {len(rows)} processes to {args.output}")


if __name__ == "__main__":
    main()
