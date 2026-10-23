"""Build and measure isolated Nuitka candidates without changing released packages.

Use the same CPython 3.14 interpreter/environment for build, baseline and candidate.
Runtime dependencies must first be installed from uv.lock (uv export --locked).
"""

import argparse
from datetime import UTC, datetime
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import resource
import statistics
import subprocess
import sys
import time

from tools.analysis.interpreter_study import runtime_metadata

ROOT = Path(__file__).resolve().parents[2]
NUITKA_VERSION = "4.3.1"


def source_hashes():
    files = [
        *(
            path
            for directory in ("src", "data", "config", "redis", "tools/compression")
            for path in sorted((ROOT / directory).rglob("*"))
            if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"
        ),
        ROOT / "archives/map_data.xz",
        ROOT / "uv.lock",
        ROOT / "tools/analysis/nuitka_entry.py",
        ROOT / "tools/analysis/interpreter_study.py",
    ]
    return {
        str(path.relative_to(ROOT)): hashlib.file_digest(path.open("rb"), "sha256").hexdigest()
        for path in files
    }


def build(args):
    version = importlib.metadata.version("nuitka")
    if version != NUITKA_VERSION:
        raise RuntimeError(f"Use nuitka=={NUITKA_VERSION}, found {version}")
    if sysconfig_gil_disabled():
        raise RuntimeError(
            "Study uses conventional CPython; do not silently compare a free-threaded interpreter"
        )
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    command = [
        sys.executable,
        "-m",
        "nuitka",
        str(ROOT / "tools/analysis/nuitka_entry.py"),
        f"--mode={args.mode}",
        f"--output-dir={output}",
        "--output-filename=pyao-study",
        "--jobs=4",
        "--lto=no",
        "--static-libpython=no",
        "--assume-yes-for-downloads",
        "--include-package=src",
        "--include-package=tools.compression",
        "--include-module=tools.analysis.interpreter_study",
        "--follow-import-to=src,tools",
        "--nofollow-import-to=pytest,tkinter,unittest,IPython,numpy,matplotlib",
        f"--report={output / 'compilation-report.xml'}",
    ]
    if args.mode == "standalone":
        command += [
            f"--include-data-dir={ROOT / 'src/network/protocol'}=src/network/protocol",
            f"--include-data-dir={ROOT / 'data'}=src/runtime_data/data",
            f"--include-data-dir={ROOT / 'config'}=src/runtime_data/config",
            f"--include-data-dir={ROOT / 'redis'}=src/runtime_data/redis",
            f"--include-data-files={ROOT / 'archives/map_data.xz'}=src/runtime_data/archives/map_data.xz",
            "--include-distribution-metadata=pyao-server",
        ]
    metadata = {
        "nuitka": version,
        "runtime": runtime_metadata(),
        "command": command,
        "started_at": datetime.now(UTC).isoformat(),
        "source_sha256": source_hashes(),
        "git_head": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "packages": dict(
            sorted(
                (dist.metadata["Name"], dist.version) for dist in importlib.metadata.distributions()
            )
        ),
        "compiler": subprocess.check_output(["gcc", "--version"], text=True).splitlines()[0],
        "mode": args.mode,
    }
    (output / "build.json").write_text(json.dumps(metadata, indent=2) + "\n")
    started = time.monotonic()
    with (output / "build.log").open("wb") as log:
        result = subprocess.run(
            command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, timeout=7200
        )
    metadata.update(
        {
            "exit_code": result.returncode,
            "wall_seconds": time.monotonic() - started,
            "peak_children_rss_bytes": resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
            * 1024,
            "total_build_bytes": sum(
                path.stat().st_size for path in output.rglob("*") if path.is_file()
            ),
            "source_unchanged_during_build": metadata["source_sha256"] == source_hashes(),
        }
    )
    executable = output / (
        "nuitka_entry.dist/pyao-study" if args.mode == "standalone" else "pyao-study"
    )
    metadata["executable"] = str(executable)
    if executable.is_file():
        metadata["executable_sha256"] = hashlib.file_digest(
            executable.open("rb"), "sha256"
        ).hexdigest()
        metadata["distribution_bytes"] = (
            sum(path.stat().st_size for path in executable.parent.rglob("*") if path.is_file())
            if args.mode == "standalone"
            else executable.stat().st_size
        )
    (output / "build.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print(
        json.dumps(
            {
                key: metadata.get(key)
                for key in (
                    "exit_code",
                    "wall_seconds",
                    "distribution_bytes",
                    "source_unchanged_during_build",
                )
            }
        )
    )
    if result.returncode:
        raise SystemExit(result.returncode)


def sysconfig_gil_disabled():
    import sysconfig

    return bool(sysconfig.get_config_var("Py_GIL_DISABLED"))


def compare(args):
    candidates = []
    for path in args.build:
        metadata = json.loads(path.read_text())
        if metadata.get("exit_code") != 0 or not metadata.get("source_unchanged_during_build"):
            raise RuntimeError(f"Invalid candidate: {path}")
        if metadata["source_sha256"] != source_hashes():
            raise RuntimeError(f"Sources differ from measured candidate: {path}")
        candidates.append((metadata["mode"], [metadata["executable"], "--study-kernels"]))
    variants = [
        (
            "cpython",
            [sys.executable, str(ROOT / "tools/analysis/nuitka_entry.py"), "--study-kernels"],
        ),
        *candidates,
    ]
    results = []
    for repeat in range(args.repeats):
        order = variants[repeat % len(variants) :] + variants[: repeat % len(variants)]
        for name, command in order:
            start = time.perf_counter()
            completed = subprocess.run(
                command, cwd=ROOT, capture_output=True, text=True, check=True, timeout=180
            )
            probe = json.loads(completed.stdout)
            results.append(
                {
                    "variant": name,
                    "repeat": repeat,
                    "process_wall_seconds": time.perf_counter() - start,
                    **probe,
                }
            )
    summary = {}
    for name, _ in variants:
        probes = [row for row in results if row["variant"] == name]
        summary[name] = {
            kernel: {
                "p50_ns_median": statistics.median(
                    row["kernels"][kernel]["wall_ns"]["p50"] for row in probes
                ),
                "p50_ns_min": min(row["kernels"][kernel]["wall_ns"]["p50"] for row in probes),
                "p50_ns_max": max(row["kernels"][kernel]["wall_ns"]["p50"] for row in probes),
            }
            for kernel in probes[0]["kernels"]
        }
    args.output.write_text(
        json.dumps(
            {
                "source_sha256": source_hashes(),
                "runtime": runtime_metadata(),
                "probes": results,
                "summary": summary,
                "limitations": [
                    "Fresh process on warm filesystem; includes imports and kernels, not server startup",
                    "Same CPython build and dependencies, no free-threaded/JIT comparison",
                    "Kernel timings do not measure maximum player capacity or Redis/network speedup",
                ],
            },
            indent=2,
        )
        + "\n"
    )
    print(args.output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    builder = sub.add_parser("build")
    builder.add_argument("--mode", choices=("accelerated", "standalone"), required=True)
    builder.add_argument("--output", type=Path, required=True)
    comparison = sub.add_parser("compare")
    comparison.add_argument("--build", type=Path, action="append", required=True)
    comparison.add_argument("--output", type=Path, required=True)
    comparison.add_argument("--repeats", type=int, default=5)
    args = parser.parse_args()
    if args.command == "build":
        build(args)
    else:
        compare(args)


if __name__ == "__main__":
    main()
