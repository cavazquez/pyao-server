"""Comando de equipar/desequipar item."""

from dataclasses import dataclass
from time import time

from src.commands.base import Command


@dataclass
class EquipItemCommand(Command):
    """Comando de equipar/desequipar item (solo datos).

    Attributes:
        user_id: ID del jugador que equipa/desequipa.
        slot: Slot del inventario a equipar/desequipar.
        timestamp: Timestamp del comando.
    """

    user_id: int
    slot: int
    timestamp: float | None = None

    def __post_init__(self) -> None:
        """Inicializa timestamp si no se proporciona."""
        if self.timestamp is None:
            self.timestamp = time()
