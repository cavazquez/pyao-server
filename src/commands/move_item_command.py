"""Comando para mover items en el inventario."""

from dataclasses import dataclass
from time import time

from src.commands.base import Command


@dataclass
class MoveItemCommand(Command):
    """Comando para mover un item de un slot a otro en el inventario.

    Attributes:
        user_id: ID del jugador que mueve el item.
        old_slot: Slot de origen (1-based).
        new_slot: Slot de destino (1-based).
        timestamp: Timestamp del comando.
    """

    user_id: int
    old_slot: int
    new_slot: int
    timestamp: float | None = None

    def __post_init__(self) -> None:
        """Inicializa timestamp si no se proporciona."""
        if self.timestamp is None:
            self.timestamp = time()
