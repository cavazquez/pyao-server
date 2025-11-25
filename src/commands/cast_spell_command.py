"""Comando de lanzar hechizo."""

from dataclasses import dataclass
from time import time

from src.commands.base import Command


@dataclass
class CastSpellCommand(Command):
    """Comando de lanzar hechizo (solo datos).

    Attributes:
        user_id: ID del jugador que lanza el hechizo.
        slot: Slot del spellbook donde está el hechizo.
        target_x: Coordenada X del objetivo (None si se calcula según heading).
        target_y: Coordenada Y del objetivo (None si se calcula según heading).
        timestamp: Timestamp del comando.
    """

    user_id: int
    slot: int
    target_x: int | None = None
    target_y: int | None = None
    timestamp: float | None = None

    def __post_init__(self) -> None:
        """Inicializa timestamp si no se proporciona."""
        if self.timestamp is None:
            self.timestamp = time()
