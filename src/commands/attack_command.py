"""Comando de ataque."""

from dataclasses import dataclass
from time import time

from src.commands.base import Command


@dataclass
class AttackCommand(Command):
    """Comando de ataque (solo datos).

    Attributes:
        user_id: ID del jugador que ataca.
        target_x: Coordenada X del objetivo.
        target_y: Coordenada Y del objetivo.
        map_id: ID del mapa donde ocurre el ataque.
        timestamp: Timestamp del comando.
    """

    user_id: int
    target_x: int
    target_y: int
    map_id: int
    timestamp: float | None = None

    def __post_init__(self) -> None:
        """Inicializa timestamp si no se proporciona."""
        if self.timestamp is None:
            self.timestamp = time()
