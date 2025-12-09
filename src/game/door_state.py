"""Estado de puertas cerradas por mapa."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class DoorState:
    """Gestiona puertas cerradas por mapa."""

    def __init__(self) -> None:
        """Inicializa el storage interno."""
        self._closed: dict[int, set[tuple[int, int]]] = {}

    @property
    def data(self) -> dict[int, set[tuple[int, int]]]:
        """Acceso directo al storage (compatibilidad)."""
        return self._closed

    def block(self, map_id: int, x: int, y: int) -> None:
        """Marca una puerta como cerrada."""
        if map_id not in self._closed:
            self._closed[map_id] = set()
        self._closed[map_id].add((x, y))
        logger.info(
            "🚪 PUERTA CERRADA: Mapa %d (%d, %d) - Total puertas cerradas: %d",
            map_id,
            x,
            y,
            len(self._closed.get(map_id, set())),
        )

    def unblock(self, map_id: int, x: int, y: int) -> None:
        """Marca una puerta como abierta."""
        if map_id in self._closed:
            self._closed[map_id].discard((x, y))
            logger.info(
                "🚪 PUERTA ABIERTA: Mapa %d (%d, %d) - Total puertas cerradas: %d",
                map_id,
                x,
                y,
                len(self._closed.get(map_id, set())),
            )

    def is_closed(self, map_id: int, x: int, y: int) -> bool:
        """Retorna True si la puerta está cerrada.

        Returns:
            bool: True si está cerrada, False en caso contrario.
        """
        if map_id not in self._closed:
            return False
        return (x, y) in self._closed[map_id]

    def clear_map(self, map_id: int) -> None:
        """Limpia todas las puertas de un mapa."""
        self._closed.pop(map_id, None)

    def clear_all(self) -> None:
        """Limpia el estado completo."""
        self._closed.clear()
