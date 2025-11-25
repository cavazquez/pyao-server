"""Comando para aceptar una invitación a la party."""

from dataclasses import dataclass
from time import time

from src.commands.base import Command


@dataclass
class PartyAcceptCommand(Command):
    """Comando para aceptar una invitación a la party (solo datos).

    Attributes:
        user_id: ID del jugador que acepta la invitación.
        leader_username: Nombre del líder de la party.
        timestamp: Timestamp del comando.
    """

    user_id: int
    leader_username: str
    timestamp: float | None = None

    def __post_init__(self) -> None:
        """Inicializa timestamp si no se proporciona."""
        if self.timestamp is None:
            self.timestamp = time()
