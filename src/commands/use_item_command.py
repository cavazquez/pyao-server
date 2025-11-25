"""Comando de usar item."""

from dataclasses import dataclass
from time import time

from src.commands.base import Command


@dataclass
class UseItemCommand(Command):
    """Comando de usar item (solo datos).

    Attributes:
        user_id: ID del jugador que usa el item.
        slot: Slot del inventario donde está el item.
        username: Username del jugador (opcional, para actualización visual).
        timestamp: Timestamp del comando.
    """

    user_id: int
    slot: int
    username: str | None = None
    timestamp: float | None = None

    def __post_init__(self) -> None:
        """Inicializa timestamp si no se proporciona."""
        if self.timestamp is None:
            self.timestamp = time()
