"""Comando para invitar a un usuario a la party."""

from dataclasses import dataclass
from time import time

from src.commands.base import Command


@dataclass
class PartyJoinCommand(Command):
    """Comando para invitar a un usuario a la party (solo datos).

    Attributes:
        user_id: ID del jugador que invita.
        target_username: Nombre del usuario a invitar.
        timestamp: Timestamp del comando.
    """

    user_id: int
    target_username: str
    timestamp: float | None = None

    def __post_init__(self) -> None:
        """Inicializa timestamp si no se proporciona."""
        if self.timestamp is None:
            self.timestamp = time()
