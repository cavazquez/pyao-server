"""Comando para mensaje de grito (chat con rango ampliado)."""

from dataclasses import dataclass
from time import time

from src.commands.base import Command


@dataclass
class YellCommand(Command):
    """Comando para grito (solo datos).

    Attributes:
        user_id: ID del usuario que envía el grito.
        message: Mensaje de grito.
        timestamp: Timestamp del comando.
    """

    user_id: int
    message: str
    timestamp: float | None = None

    def __post_init__(self) -> None:
        """Inicializa timestamp si no se proporciona."""
        if self.timestamp is None:
            self.timestamp = time()
