"""Comando para click en inventario."""

from dataclasses import dataclass
from time import time

from src.commands.base import Command


@dataclass
class InventoryClickCommand(Command):
    """Comando para click en un slot del inventario (solo datos).

    Attributes:
        user_id: ID del jugador que hace click.
        slot: Slot del inventario clickeado.
        timestamp: Timestamp del comando.
    """

    user_id: int
    slot: int
    timestamp: float | None = None

    def __post_init__(self) -> None:
        """Inicializa timestamp si no se proporciona."""
        if self.timestamp is None:
            self.timestamp = time()
