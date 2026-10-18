"""Comando de usar item."""

from dataclasses import dataclass, field
from time import time

from src.commands.base import Command
from src.utils.gold_atomic import operation_id


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
    operation_id: str = field(default_factory=operation_id)

    def __post_init__(self) -> None:
        """Inicializa timestamp si no se proporciona."""
        if self.timestamp is None:
            self.timestamp = time()
