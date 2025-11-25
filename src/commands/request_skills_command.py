"""Comando para solicitar habilidades del jugador."""

from dataclasses import dataclass
from time import time

from src.commands.base import Command


@dataclass
class RequestSkillsCommand(Command):
    """Comando para solicitar habilidades del jugador.

    Attributes:
        user_id: ID del usuario.
        timestamp: Timestamp del comando.
    """

    user_id: int
    timestamp: float | None = None

    def __post_init__(self) -> None:
        """Inicializa timestamp si no se proporciona."""
        if self.timestamp is None:
            self.timestamp = time()
