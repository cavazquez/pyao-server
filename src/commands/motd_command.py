"""Comando para solicitar el mensaje del día."""

from dataclasses import dataclass
from time import time

from src.commands.base import Command


@dataclass
class MotdCommand(Command):
    """Comando para solicitar el mensaje del día.

    Attributes:
        timestamp: Timestamp del comando.
    """

    timestamp: float | None = None

    def __post_init__(self) -> None:
        """Inicializa timestamp si no se proporciona."""
        if self.timestamp is None:
            self.timestamp = time()
