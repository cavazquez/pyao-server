"""Comando para enviar mensaje a la party."""

from dataclasses import dataclass
from time import time

from src.commands.base import Command


@dataclass
class PartyMessageCommand(Command):
    """Comando para enviar mensaje a la party (solo datos).

    Attributes:
        user_id: ID del jugador que envía el mensaje.
        message: Mensaje a enviar.
        timestamp: Timestamp del comando.
    """

    user_id: int
    message: str
    timestamp: float | None = None

    def __post_init__(self) -> None:
        """Inicializa timestamp si no se proporciona."""
        if self.timestamp is None:
            self.timestamp = time()
