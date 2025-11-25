"""Comando para expulsar a un miembro de la party."""

from dataclasses import dataclass
from time import time

from src.commands.base import Command


@dataclass
class PartyKickCommand(Command):
    """Comando para expulsar a un miembro de la party (solo datos).

    Attributes:
        user_id: ID del líder que expulsa.
        target_username: Nombre del usuario a expulsar.
        timestamp: Timestamp del comando.
    """

    user_id: int
    target_username: str
    timestamp: float | None = None

    def __post_init__(self) -> None:
        """Inicializa timestamp si no se proporciona."""
        if self.timestamp is None:
            self.timestamp = time()
