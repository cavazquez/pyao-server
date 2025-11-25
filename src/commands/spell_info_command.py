"""Comando para solicitar información de un hechizo."""

from dataclasses import dataclass
from time import time

from src.commands.base import Command


@dataclass
class SpellInfoCommand(Command):
    """Comando para solicitar información de un hechizo.

    Attributes:
        user_id: ID del usuario.
        slot: Slot del hechizo en el libro de hechizos.
        timestamp: Timestamp del comando.
    """

    user_id: int
    slot: int
    timestamp: float | None = None

    def __post_init__(self) -> None:
        """Inicializa timestamp si no se proporciona."""
        if self.timestamp is None:
            self.timestamp = time()
