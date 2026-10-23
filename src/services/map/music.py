"""Música normal del mundo independiente de las superposiciones de GM."""

import tomllib
from functools import cache

from src.runtime_paths import data_dir

AVAILABLE_TRACKS = frozenset({0, *range(1, 29), *range(50, 76), *range(77, 135)})


@cache
def tracks() -> dict[int, int]:
    """Resuelve y valida una pista explícita para cada mapa distribuido.

    Returns:
        Mapa completo de IDs a pistas disponibles en el manifiesto del cliente.

    Raises:
        ValueError: Si el balance referencia un tipo o pista inexistente.
    """
    root = data_dir() / "world"
    with (root / "map_metadata.toml").open("rb") as stream:
        metadata = tomllib.load(stream)
    with (root / "map_music.toml").open("rb") as stream:
        policy = tomllib.load(stream)
    result = {}
    for key, entry in metadata.items():
        map_id = int(key.removeprefix("map_"))
        track = policy["maps"].get(str(map_id), policy["types"].get(entry["type"]))
        if type(track) is not int or track not in AVAILABLE_TRACKS:
            message = f"Música inválida para mapa {map_id}"
            raise ValueError(message)
        result[map_id] = track
    return result
