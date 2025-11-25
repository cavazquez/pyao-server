"""Comando para desconexión de usuarios."""

from dataclasses import dataclass
from time import time

from src.commands.base import Command


@dataclass
class QuitCommand(Command):
    """Comando para desconexión de usuarios.

    Attributes:
        user_id: ID del usuario.
        username: Nombre de usuario.
        timestamp: Timestamp del comando.
    """

    user_id: int
    username: str
    timestamp: float | None = None

    def __post_init__(self) -> None:
        """Inicializa timestamp si no se proporciona."""
        if self.timestamp is None:
            self.timestamp = time()
