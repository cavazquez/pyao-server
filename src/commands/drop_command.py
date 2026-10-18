"""Comando de soltar item."""

from dataclasses import dataclass, field
from time import time

from src.commands.base import Command
from src.utils.gold_atomic import operation_id as new_operation_id


@dataclass
class DropCommand(Command):
    """Comando de soltar item del inventario al suelo (solo datos).

    Attributes:
        user_id: ID del jugador que suelta el item.
        slot: Slot del inventario.
        quantity: Cantidad a soltar.
        timestamp: Timestamp del comando.
    """

    user_id: int
    slot: int
    quantity: int
    timestamp: float | None = None
    operation_id: str = field(default_factory=new_operation_id)
    notified: bool = False
    origin: tuple[int, int, int] | None = None
    expected_item_id: int | None = None

    def __post_init__(self) -> None:
        """Inicializa timestamp si no se proporciona."""
        if self.timestamp is None:
            self.timestamp = time()
