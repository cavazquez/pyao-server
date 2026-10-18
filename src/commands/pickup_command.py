"""Comando de recoger item."""

from dataclasses import dataclass, field
from time import time

from src.commands.base import Command
from src.utils.gold_atomic import operation_id as new_operation_id


@dataclass
class PickupCommand(Command):
    """Comando de recoger item del suelo (solo datos).

    Attributes:
        user_id: ID del jugador que recoge el item.
        timestamp: Timestamp del comando.
    """

    user_id: int
    timestamp: float | None = None
    operation_id: str = field(default_factory=new_operation_id)
    notified: bool = False
    origin: tuple[int, int, int] | None = None
    expected_item_id: int | None = None
    expected_stack_id: str | None = None

    def __post_init__(self) -> None:
        """Inicializa timestamp si no se proporciona."""
        if self.timestamp is None:
            self.timestamp = time()
