"""Comando para solicitar lista de jugadores online."""

from dataclasses import dataclass
from time import time

from src.commands.base import Command


@dataclass
class OnlineCommand(Command):
    """Comando para solicitar lista de jugadores online.

    Attributes:
        user_id: ID del usuario que solicita la lista.
        timestamp: Timestamp del comando.
    """

    user_id: int
    timestamp: float | None = None

    def __post_init__(self) -> None:
        """Inicializa timestamp si no se proporciona."""
        if self.timestamp is None:
            self.timestamp = time()
