"""Comando para click izquierdo en el mapa."""

from dataclasses import dataclass
from time import time

from src.commands.base import Command


@dataclass
class LeftClickCommand(Command):
    """Comando para click izquierdo en el mapa (solo datos).

    Attributes:
        user_id: ID del jugador que hace click.
        map_id: ID del mapa donde está el jugador.
        x: Coordenada X del click.
        y: Coordenada Y del click.
        timestamp: Timestamp del comando.
    """

    user_id: int
    map_id: int
    x: int
    y: int
    timestamp: float | None = None

    def __post_init__(self) -> None:
        """Inicializa timestamp si no se proporciona."""
        if self.timestamp is None:
            self.timestamp = time()
