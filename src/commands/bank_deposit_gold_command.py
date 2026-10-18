"""Comando de depositar oro en el banco."""

from dataclasses import dataclass, field
from time import time

from src.commands.base import Command
from src.utils.gold_atomic import operation_id as new_operation_id


@dataclass
class BankDepositGoldCommand(Command):
    """Comando de depositar oro en el banco (solo datos).

    Attributes:
        user_id: ID del jugador que deposita.
        amount: Cantidad de oro a depositar.
        timestamp: Timestamp del comando.
    """

    user_id: int
    amount: int
    timestamp: float | None = None
    operation_id: str = field(default_factory=new_operation_id)

    def __post_init__(self) -> None:
        """Inicializa timestamp si no se proporciona."""
        if self.timestamp is None:
            self.timestamp = time()
