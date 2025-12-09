"""Índice de ocupación de tiles (jugadores y NPCs)."""

from __future__ import annotations

import logging
from collections.abc import Iterable

logger = logging.getLogger(__name__)


class TileOccupation:
    """Gestiona ocupación de tiles para jugadores y NPCs."""

    def __init__(self) -> None:
        """Inicializa el storage interno."""
        self._data: dict[tuple[int, int, int], str] = {}

    @property
    def data(self) -> dict[tuple[int, int, int], str]:
        """Acceso directo al storage (compatibilidad)."""
        return self._data

    def is_occupied(self, map_id: int, x: int, y: int) -> bool:
        """Devuelve True si el tile está ocupado.

        Returns:
            bool: True si está ocupado, False en caso contrario.
        """
        return (map_id, x, y) in self._data

    def get_occupant(self, map_id: int, x: int, y: int) -> str | None:
        """Retorna la etiqueta del ocupante o None.

        Returns:
            str | None: Etiqueta del ocupante o None.
        """
        return self._data.get((map_id, x, y))

    def occupy_npc(self, map_id: int, x: int, y: int, instance_id: str) -> None:
        """Marca tile para un NPC, fallando si está ocupado.

        Raises:
            ValueError: si el tile ya está ocupado.
        """
        key = (map_id, x, y)
        if key in self._data:
            occupant = self._data[key]
            msg = f"tile ya ocupado por {occupant}"
            raise ValueError(msg)
        self._data[key] = f"npc:{instance_id}"

    def move_npc(
        self, map_id: int, old_x: int, old_y: int, new_x: int, new_y: int, instance_id: str
    ) -> None:
        """Mueve un NPC liberando el tile anterior."""
        old_key = (map_id, old_x, old_y)
        self._data.pop(old_key, None)
        self._data[map_id, new_x, new_y] = f"npc:{instance_id}"

    def remove_npc(self, map_id: int, x: int, y: int) -> None:
        """Libera un tile ocupado por NPC (si existe)."""
        self._data.pop((map_id, x, y), None)

    def remove_npc_by_instance(self, instance_id: str, map_id: int | None = None) -> None:
        """Libera tiles ocupados por una instancia de NPC."""
        self._remove_by_prefix(f"npc:{instance_id}", map_id)

    def remove_player(self, user_id: int, map_id: int | None = None) -> None:
        """Libera tiles ocupados por un jugador."""
        self._remove_by_prefix(f"player:{user_id}", map_id)

    def occupy_player(self, map_id: int, x: int, y: int, user_id: int) -> None:
        """Marca tile para un jugador (sobrescribe si existía)."""
        self._data[map_id, x, y] = f"player:{user_id}"

    def move_player(
        self, map_id: int, old_x: int, old_y: int, new_x: int, new_y: int, user_id: int
    ) -> None:
        """Mueve un jugador liberando tile previo."""
        old_key = (map_id, old_x, old_y)
        self._data.pop(old_key, None)
        self._data[map_id, new_x, new_y] = f"player:{user_id}"

    def _remove_by_prefix(self, prefix: str, map_id: int | None) -> None:
        keys_to_remove: list[tuple[int, int, int]] = []
        for key, occupant in self._data.items():
            if (map_id is None or key[0] == map_id) and occupant == prefix:
                keys_to_remove.append(key)
        for key in keys_to_remove:
            self._data.pop(key, None)

    def clear_map(self, map_id: int) -> None:
        """Limpia todas las ocupaciones de un mapa."""
        keys_to_remove: Iterable[tuple[int, int, int]] = [k for k in self._data if k[0] == map_id]
        for key in list(keys_to_remove):
            self._data.pop(key, None)
