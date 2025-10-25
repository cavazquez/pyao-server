"""Herramienta para descomprimir archivos ``map_data.xz`` generados por ``compress_map_data``."""

from __future__ import annotations

import argparse
import io
import shutil
from collections.abc import Iterable
from compression import lzma
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_MARKER_FILE = b"FILE:"
_MARKER_SIZE = b"SIZE:"
_END_SUFFIX = b"END\n"


def _read_exact(buffer: io.BufferedReader, size: int) -> bytes:
    """Lee exactamente ``size`` bytes.

    Raises:
        ValueError: Si la cantidad de bytes leídos difiere de ``size``.

    Returns:
        bytes: Los datos leídos.
    """
    data = buffer.read(size)
    if len(data) != size:
        msg = f"Se esperaban {size} bytes pero se recibieron {len(data)}"
        raise ValueError(msg)
    return data


def decompress_map_data(archive_path: Path, target_dir: Path, overwrite: bool) -> None:
    """Descomprime ``map_data.xz`` en el directorio destino.

    Raises:
        FileNotFoundError: Si el archivo comprimido no existe.
        FileExistsError: Si el destino existe y no se permite sobrescritura.
    """
    if not archive_path.exists() or not archive_path.is_file():
        msg = f"Archivo comprimido inexistente: {archive_path}"
        raise FileNotFoundError(msg)

    if target_dir.exists():
        if not overwrite:
            msg = f"El directorio destino ya existe: {target_dir}. Use --overwrite para reemplazar."
            raise FileExistsError(msg)
        shutil.rmtree(target_dir)

    target_dir.mkdir(parents=True, exist_ok=True)
    target_resolved = target_dir.resolve()

    with lzma.open(archive_path, "rb") as in_f:
        buffer = io.BufferedReader(in_f)

        for file_entry in _iter_archive_entries(buffer):
            destination = _prepare_destination(target_resolved, file_entry.relative_path)
            destination.parent.mkdir(parents=True, exist_ok=True)
            with destination.open("wb") as out_f:
                out_f.write(file_entry.data)


@dataclass(slots=True)
class _ArchiveEntry:
    """Representa un archivo individual dentro del contenedor comprimido."""

    relative_path: Path
    data: bytes


def _iter_archive_entries(buffer: io.BufferedReader[Any]) -> Iterable[_ArchiveEntry]:
    """Produce entradas del archivo comprimido de forma secuencial.

    Yields:
        _ArchiveEntry: Objeto con ruta relativa y contenido binario.

    Raises:
        ValueError: Si se detecta un marcador o formato inválido.
    """
    while True:
        header = buffer.readline()
        if not header:
            break
        if not header.startswith(_MARKER_FILE):
            msg = "Formato inválido: se esperaba marcador FILE"
            raise ValueError(msg)

        relative_path_str = header[len(_MARKER_FILE) :].strip().decode("utf-8")
        if not relative_path_str:
            msg = "Ruta relativa vacía en chunk comprimido"
            raise ValueError(msg)

        size_line = buffer.readline()
        if not size_line.startswith(_MARKER_SIZE):
            msg = "Formato inválido: se esperaba marcador SIZE"
            raise ValueError(msg)
        size = int(size_line[len(_MARKER_SIZE) :])

        data = _read_exact(buffer, size)
        newline = buffer.read(1)
        if newline != b"\n":
            msg = "Formato inválido: separador tras contenido"
            raise ValueError(msg)
        end_line = buffer.readline()
        if end_line != _END_SUFFIX:
            msg = "Formato inválido: marcador END ausente"
            raise ValueError(msg)

        yield _ArchiveEntry(Path(relative_path_str), data)


def _prepare_destination(base_dir: Path, relative_path: Path) -> Path:
    """Valida y retorna la ruta destino para una entrada.

    Raises:
        ValueError: Si la ruta apunta fuera del directorio base o es inválida.

    Returns:
        Path: Ruta absoluta validada dentro del directorio base.
    """
    if relative_path.is_absolute() or any(part in {"..", ""} for part in relative_path.parts):
        msg = "Ruta inválida detectada durante la descompresión"
        raise ValueError(msg)

    destination = (base_dir / relative_path).resolve()
    try:
        destination.relative_to(base_dir)
    except ValueError as exc:
        msg = "Ruta fuera del directorio destino detectada"
        raise ValueError(msg) from exc

    return destination


def main() -> None:
    """Punto de entrada CLI para descomprimir ``map_data.xz``."""
    parser = argparse.ArgumentParser(
        description="Descomprime map_data.xz generado por compress_map_data"
    )
    parser.add_argument(
        "--archive",
        type=Path,
        default=Path("archives/map_data.xz"),
        help="Archivo LZMA a descomprimir",
    )
    parser.add_argument(
        "--target",
        type=Path,
        default=Path("map_data"),
        help="Directorio destino para los archivos extraídos",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Permite reemplazar el directorio destino si existe",
    )

    args = parser.parse_args()
    decompress_map_data(args.archive, args.target, args.overwrite)


if __name__ == "__main__":
    main()
