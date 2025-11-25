"""Comando para cambio de dirección."""

from dataclasses import dataclass
from time import time

from src.commands.base import Command


@dataclass
class ChangeHeadingCommand(Command):
    """Comando para cambio de dirección del personaje (solo datos).

    Attributes:
        user_id: ID del usuario.
        heading: Dirección (1=Norte, 2=Este, 3=Sur, 4=Oeste).
        timestamp: Timestamp del comando.
    """

    user_id: int
    heading: int
    timestamp: float | None = None

    def __post_init__(self) -> None:
        """Inicializa timestamp si no se proporciona."""
        if self.timestamp is None:
            self.timestamp = time()
