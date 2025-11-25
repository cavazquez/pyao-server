"""Comando para crear una party."""

from dataclasses import dataclass
from time import time

from src.commands.base import Command


@dataclass
class PartyCreateCommand(Command):
    """Comando para crear una party (solo datos).

    Attributes:
        user_id: ID del jugador que crea la party.
        timestamp: Timestamp del comando.
    """

    user_id: int
    timestamp: float | None = None

    def __post_init__(self) -> None:
        """Inicializa timestamp si no se proporciona."""
        if self.timestamp is None:
            self.timestamp = time()
