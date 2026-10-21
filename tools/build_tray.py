"""Compila el pequeño puente GTK/Ayatana para la arquitectura nativa del paquete."""

import argparse
from pathlib import Path
import shlex
import subprocess


def build(source: Path, output: Path) -> Path:
    """No incorpora Python al cliente: el resultado es un ejecutable C nativo.

    Returns:
        Ejecutable del puente de bandeja.
    """
    flags = shlex.split(
        subprocess.check_output(
            ["pkg-config", "--cflags", "--libs", "gtk+-3.0", "ayatana-appindicator3-0.1"], text=True
        )
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "cc",
            "-std=c11",
            "-O2",
            "-Wall",
            "-Wextra",
            "-Werror",
            str(source),
            "-o",
            str(output),
            *flags,
        ],
        check=True,
    )
    return output


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    source = root / "desktop/tray_linux.c"
    if not source.is_file():
        source = root / "src/runtime_data/data/desktop/tray_linux.c"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=source)
    parser.add_argument("--output", type=Path, default=Path("build/desktop/pyao-tray"))
    args = parser.parse_args()
    print(build(args.source, args.output))
