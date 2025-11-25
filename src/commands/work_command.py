"""Comando de trabajo (talar, minar, pescar)."""

from dataclasses import dataclass
from time import time

from src.commands.base import Command


@dataclass
class WorkCommand(Command):
    """Comando de trabajo (solo datos).

    Attributes:
        user_id: ID del jugador que trabaja.
        map_id: ID del mapa donde está trabajando.
        target_x: Coordenada X objetivo.
        target_y: Coordenada Y objetivo.
        timestamp: Timestamp del comando.
    """

    user_id: int
    map_id: int
    target_x: int
    target_y: int
    timestamp: float | None = None

    def __post_init__(self) -> None:
        """Inicializa timestamp si no se proporciona."""
        if self.timestamp is None:
            self.timestamp = time()
