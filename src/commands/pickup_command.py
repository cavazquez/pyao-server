"""Comando de recoger item."""

from dataclasses import dataclass
from time import time

from src.commands.base import Command


@dataclass
class PickupCommand(Command):
    """Comando de recoger item del suelo (solo datos).

    Attributes:
        user_id: ID del jugador que recoge el item.
        timestamp: Timestamp del comando.
    """

    user_id: int
    timestamp: float | None = None

    def __post_init__(self) -> None:
        """Inicializa timestamp si no se proporciona."""
        if self.timestamp is None:
            self.timestamp = time()
