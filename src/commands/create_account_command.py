"""Comando para creación de cuenta."""

from dataclasses import dataclass
from time import time

from src.commands.base import Command


@dataclass
class CreateAccountCommand(Command):
    """Comando para creación de cuenta (solo datos).

    Attributes:
        username: Nombre de usuario.
        password: Contraseña en texto plano.
        email: Email del usuario.
        char_data: Datos del personaje (race, gender, job, head, home).
        timestamp: Timestamp del comando.
    """

    username: str
    password: str
    email: str
    char_data: dict[str, int]
    timestamp: float | None = None

    def __post_init__(self) -> None:
        """Inicializa timestamp si no se proporciona."""
        if self.timestamp is None:
            self.timestamp = time()
