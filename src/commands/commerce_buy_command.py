"""Comando de comprar item."""

from dataclasses import dataclass
from time import time

from src.commands.base import Command


@dataclass
class CommerceBuyCommand(Command):
    """Comando de comprar item del mercader (solo datos).

    Attributes:
        user_id: ID del jugador que compra.
        slot: Slot del mercader a comprar.
        quantity: Cantidad a comprar.
        timestamp: Timestamp del comando.
    """

    user_id: int
    slot: int
    quantity: int
    timestamp: float | None = None

    def __post_init__(self) -> None:
        """Inicializa timestamp si no se proporciona."""
        if self.timestamp is None:
            self.timestamp = time()
