#!/usr/bin/env python3
"""Construye el Snap de servidor desde un commit limpio con procedencia verificable."""

import argparse
import hashlib
import json
import subprocess
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    """Verifica fuente y herramienta antes de invocar el proveedor aislado."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arch", choices=["amd64", "arm64"], required=True)
    args = parser.parse_args()
    version = subprocess.check_output(["snapcraft", "--version"], text=True).strip()
    if version != "snapcraft 9.1.4":
        raise SystemExit(f"Se requiere snapcraft 9.1.4; se encontró {version}")
    if subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT):
        raise SystemExit("La publicación requiere un checkout limpio")
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    metadata = tomllib.loads((ROOT / "pyproject.toml").read_text())
    provenance = {
        "version": metadata["project"]["version"],
        "commit": commit,
        "dirty": False,
        "architecture": args.arch,
        "snapcraft": "9.1.4",
        "uv": "0.13.1",
        "uv_lock_sha256": hashlib.sha256((ROOT / "uv.lock").read_bytes()).hexdigest(),
    }
    (ROOT / "snap/pyao-source.json").write_text(json.dumps(provenance, indent=2) + "\n")
    subprocess.run(
        ["snapcraft", "pack", "--use-lxd", f"--build-for={args.arch}", "--verbosity=brief"],
        cwd=ROOT,
        check=True,
    )


if __name__ == "__main__":
    main()
