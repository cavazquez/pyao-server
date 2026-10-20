"""Prepara e inspecciona la misma caché compacta que consume el servidor.

Los archivos fuente y archives/map_data.xz conservan el mundo completo. Esta
herramienta sólo genera terreno derivado; no sustituye transiciones ni catálogos.
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from src.runtime_paths import maps_dir, state_dir
from src.services.map.binary_cache import COMPACT_CACHE_NAME, MapBinaryCache
from src.services.map.map_bulk_resources_loader import run_load_all_maps

logger = logging.getLogger(__name__)


def _cache(source: Path | None, destination: Path | None) -> MapBinaryCache:
    return MapBinaryCache(
        maps_dir() if source is None else source,
        {},
        {},
        {},
        cache_dir=state_dir() / "map_binary" if destination is None else destination,
    )


def convert_json_to_binary(
    map_data_dir: Path | None = None, map_binary_dir: Path | None = None
) -> bool:
    """Genera terrain-v1.msgpack mediante el codificador y cargador del runtime.

    Returns:
        Si se construyó una caché con recursos sin alterar las fuentes.
    """
    cache = _cache(map_data_dir, map_binary_dir)
    if not cache.maps_dir.is_dir():
        logger.error("Directorio de mapas inexistente: %s", cache.maps_dir)
        return False
    run_load_all_maps(cache.maps_dir, cache.resources, cache.signs, cache.doors, log=logger)
    if not cache.resources:
        logger.error("No hay recursos para generar la caché: %s", cache.maps_dir)
        return False
    return cache.generate_binary_cache()


def check_binary_needs_rebuild(
    map_data_dir: Path | None = None, map_binary_dir: Path | None = None
) -> bool:
    """Comprueba formato, contenido y huellas mediante el validador del runtime.

    Returns:
        Si falta una caché compacta válida para esas fuentes.
    """
    return not _cache(map_data_dir, map_binary_dir).try_load_from_binary()


def ensure_binary_maps(
    map_data_dir: Path | None = None,
    map_binary_dir: Path | None = None,
    force: bool = False,
) -> bool:
    """Prepara la caché vigente; conserva sin usar archivos del formato anterior.

    Returns:
        Si la caché compacta está lista para el servidor.
    """
    if not force and not check_binary_needs_rebuild(map_data_dir, map_binary_dir):
        return True
    return convert_json_to_binary(map_data_dir, map_binary_dir)


def cmd_convert(args: argparse.Namespace) -> int:
    """Ejecuta la conversión y comunica su resultado.

    Returns:
        Cero si se generó la caché compacta.
    """
    return 0 if convert_json_to_binary(args.map_data, args.map_binary) else 1


def cmd_status(args: argparse.Namespace) -> int:
    """Verifica la caché sin regenerarla.

    Returns:
        Cero sólo si el servidor puede cargar la caché elegida.
    """
    cache = _cache(args.map_data, args.map_binary)
    valid = cache.try_load_from_binary()
    print(f"Archivo: {cache.cache_dir / COMPACT_CACHE_NAME}")
    print(f"Estado: {'actualizado' if valid else 'ausente, inválido o desactualizado'}")
    if valid:
        print(f"Mapas: {len(cache.resources)}")
    return 0 if valid else 1


def main() -> None:
    """Conserva convert/status y permite elegir rutas independientes del cwd."""
    parser = argparse.ArgumentParser(
        description="Prepara la caché compacta de terreno del servidor"
    )
    parser.add_argument("--map-data", type=Path)
    parser.add_argument("--map-binary", type=Path)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("convert", help="Genera terrain-v1.msgpack")
    subparsers.add_parser("status", help="Valida caché y hashes de las fuentes")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    raise SystemExit(cmd_convert(args) if args.command == "convert" else cmd_status(args))


if __name__ == "__main__":
    main()
