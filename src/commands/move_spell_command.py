"""Comando para mover hechizos en el libro."""

from dataclasses import dataclass
from time import time

from src.commands.base import Command


@dataclass
class MoveSpellCommand(Command):
    """Comando para mover un hechizo en el libro (solo datos).

    Attributes:
        user_id: ID del jugador que mueve el hechizo.
        slot: Slot del hechizo a mover.
        upwards: True para mover hacia arriba, False para mover hacia abajo.
        timestamp: Timestamp del comando.
    """

    user_id: int
    slot: int
    upwards: bool
    timestamp: float | None = None

    def __post_init__(self) -> None:
        """Inicializa timestamp si no se proporciona."""
        if self.timestamp is None:
            self.timestamp = time()
