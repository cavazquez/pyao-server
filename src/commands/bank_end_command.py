"""Comando para cerrar la ventana del banco."""

from dataclasses import dataclass
from time import time

from src.commands.base import Command


@dataclass
class BankEndCommand(Command):
    """Comando para cerrar la ventana del banco.

    Attributes:
        user_id: ID del usuario (None si no hay sesión).
        timestamp: Timestamp del comando.
    """

    user_id: int | None
    timestamp: float | None = None

    def __post_init__(self) -> None:
        """Inicializa timestamp si no se proporciona."""
        if self.timestamp is None:
            self.timestamp = time()
