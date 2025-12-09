"""Índice de tiles de exit por mapa."""

from __future__ import annotations

from collections.abc import Iterable


class ExitIndex:
    """Gestiona tiles de salida y sus destinos."""

    def __init__(self) -> None:
        """Inicializa el storage interno."""
        self._exit_tiles: dict[tuple[int, int, int], dict[str, int]] = {}

    @property
    def data(self) -> dict[tuple[int, int, int], dict[str, int]]:
        """Acceso directo al storage (compatibilidad)."""
        return self._exit_tiles

    def update(self, exits: dict[tuple[int, int, int], dict[str, int]]) -> None:
        """Agrega/actualiza exits."""
        self._exit_tiles.update(exits)

    def get_exit_tile(self, map_id: int, x: int, y: int) -> dict[str, int] | None:
        """Retorna el destino de un exit si existe.

        Returns:
            dict[str, int] | None: destino del exit o None.
        """
        return self._exit_tiles.get((map_id, x, y))

    def get_map_ids(self) -> set[int]:
        """Mapas que tienen exits.

        Returns:
            set[int]: map_ids con exits.
        """
        return {key[0] for key in self._exit_tiles}

    def clear_map(self, map_id: int) -> None:
        """Limpia exits de un mapa."""
        keys: Iterable[tuple[int, int, int]] = [k for k in self._exit_tiles if k[0] == map_id]
        for key in list(keys):
            self._exit_tiles.pop(key, None)
