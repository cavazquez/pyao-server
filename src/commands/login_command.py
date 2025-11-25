"""Comando para login de usuario."""

from dataclasses import dataclass
from time import time

from src.commands.base import Command


@dataclass
class LoginCommand(Command):
    """Comando para login de usuario (solo datos).

    Attributes:
        username: Nombre de usuario.
        password: Contraseña en texto plano.
        timestamp: Timestamp del comando.
    """

    username: str
    password: str
    timestamp: float | None = None

    def __post_init__(self) -> None:
        """Inicializa timestamp si no se proporciona."""
        if self.timestamp is None:
            self.timestamp = time()
