"""Rasteriza los vectores propios y empaqueta PNG, ICO e ICNS reproducibles."""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import struct
import subprocess


def build(source: Path, destination: Path, name: str, *, store: bool = False) -> dict[str, str]:
    """Conserva los PNG originales dentro de los contenedores nativos.

    Returns:
        Hash SHA256 de cada tamaño y contenedor generado.

    Raises:
        RuntimeError: Si falta ImageMagick, herramienta de generación de assets.
    """
    converter = shutil.which("magick") or shutil.which("convert")
    if not converter:
        raise RuntimeError("Se necesita ImageMagick para regenerar los iconos SVG propios")
    destination.mkdir(parents=True, exist_ok=True)
    pngs = {}
    for size in (16, 24, 32, 48, 64, 128, 256, 512, 1024):
        target = destination / f"{name}-{size}.png"
        subprocess.run(
            [
                converter,
                "-background",
                "none",
                "MSVG:" + str(source),
                "-resize",
                f"{size}x{size}",
                "-strip",
                "PNG32:" + str(target),
            ],
            check=True,
        )
        pngs[size] = target.read_bytes()
    sizes = (16, 24, 32, 48, 64, 128, 256)
    offset = 6 + len(sizes) * 16
    entries = []
    for size in sizes:
        data = pngs[size]
        entries.append(
            struct.pack("<BBBBHHII", size % 256, size % 256, 0, 0, 1, 32, len(data), offset)
        )
        offset += len(data)
    ico = (
        struct.pack("<HHH", 0, 1, len(sizes))
        + b"".join(entries)
        + b"".join(pngs[size] for size in sizes)
    )
    (destination / f"{name}.ico").write_bytes(ico)
    chunks = []
    for size, kind in (
        (16, b"icp4"),
        (32, b"icp5"),
        (64, b"icp6"),
        (128, b"ic07"),
        (256, b"ic08"),
        (512, b"ic09"),
        (1024, b"ic10"),
    ):
        chunks.append(kind + struct.pack(">I", len(pngs[size]) + 8) + pngs[size])
    icns = b"".join(chunks)
    (destination / f"{name}.icns").write_bytes(b"icns" + struct.pack(">I", len(icns) + 8) + icns)
    if store:
        import math

        windows = destination / "windows"
        windows.mkdir(exist_ok=True)
        for asset, base in (("Square44x44Logo", 44), ("Square150x150Logo", 150), ("StoreLogo", 50)):
            for scale in (100, 125, 150, 200, 250, 300, 400):
                size = math.ceil(base * scale / 100)
                target = windows / f"{asset}.scale-{scale}.png"
                subprocess.run(
                    [
                        converter,
                        "-background",
                        "none",
                        "MSVG:" + str(source),
                        "-resize",
                        f"{size}x{size}",
                        "-strip",
                        "PNG32:" + str(target),
                    ],
                    check=True,
                )
                if scale == 100:
                    shutil.copy2(target, windows / (asset + ".png"))
    hashes = {
        str(path.relative_to(destination)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(destination.rglob("*"))
        if path.suffix in (".png", ".ico", ".icns", ".svg")
    }
    (destination / "manifest.json").write_text(
        json.dumps({"source": source.name, "sha256": hashes}, indent=2) + "\n"
    )
    return hashes


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--store", action="store_true")
    args = parser.parse_args()
    print(json.dumps(build(args.source, args.destination, args.name, store=args.store)))
