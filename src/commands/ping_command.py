"""Comando para ping del cliente."""

from dataclasses import dataclass
from time import time

from src.commands.base import Command


@dataclass
class PingCommand(Command):
    """Comando para ping del cliente.

    Attributes:
        timestamp: Timestamp del comando.
    """

    timestamp: float | None = None

    def __post_init__(self) -> None:
        """Inicializa timestamp si no se proporciona."""
        if self.timestamp is None:
            self.timestamp = time()
