"""Comando para solicitar información del servidor."""

from dataclasses import dataclass
from time import time

from src.commands.base import Command


@dataclass
class InformationCommand(Command):
    """Comando para solicitar información del servidor.

    Attributes:
        timestamp: Timestamp del comando.
    """

    timestamp: float | None = None

    def __post_init__(self) -> None:
        """Inicializa timestamp si no se proporciona."""
        if self.timestamp is None:
            self.timestamp = time()
