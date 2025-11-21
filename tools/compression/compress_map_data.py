"""Herramienta para comprimir la carpeta ``map_data`` usando LZMA (.xz)."""

from __future__ import annotations

import argparse
import os
from collections.abc import Iterable
from compression import lzma
from pathlib import Path


def _iter_files(base_dir: Path) -> Iterable[Path]:
    """Itera archivos dentro del directorio base en orden determinístico.

    Yields:
        Path: Rutas absolutas de cada archivo localizado.
    """
    for root, _dirs, files in os.walk(base_dir):
        for filename in sorted(files):
            yield Path(root, filename)


def compress_map_data(source_dir: Path, output_file: Path, level: int) -> None:
    """Comprime los archivos de map_data en un archivo LZMA (.xz).

    Raises:
        FileNotFoundError: Si el directorio de origen no existe o no es válido.
    """
    if not source_dir.exists() or not source_dir.is_dir():
        msg = f"Directorio de origen inexistente: {source_dir}"
        raise FileNotFoundError(msg)

    output_file.parent.mkdir(parents=True, exist_ok=True)

    preset = max(0, min(level, 9))

    with lzma.open(output_file, "wb", preset=preset, check=lzma.CHECK_CRC64) as compressor:
        for file_path in _iter_files(source_dir):
            relative = file_path.relative_to(source_dir)
            header = f"FILE:{relative.as_posix()}\n".encode()
            compressor.write(header)

            with file_path.open("rb") as in_f:
                data = in_f.read()

            size_info = f"SIZE:{len(data)}\n".encode()
            compressor.write(size_info)
            compressor.write(data)
            compressor.write(b"\nEND\n")


def main() -> None:
    """Punto de entrada CLI para comprimir la carpeta ``map_data``."""
    parser = argparse.ArgumentParser(description="Comprime map_data a LZMA (.xz)")
    parser.add_argument(
        "--source",
        type=Path,
        default=Path("map_data"),
        help="Directorio con archivos JSON de mapas",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("archives/map_data.xz"),
        help="Archivo LZMA resultante",
    )
    parser.add_argument(
        "--level",
        type=int,
        default=9,
        help="Nivel de compresión LZMA (0-9)",
    )

    args = parser.parse_args()
    compress_map_data(args.source, args.output, args.level)


if __name__ == "__main__":
    main()
