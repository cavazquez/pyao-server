"""Comando de depositar item en el banco."""

from dataclasses import dataclass
from time import time

from src.commands.base import Command


@dataclass
class BankDepositCommand(Command):
    """Comando de depositar item en el banco (solo datos).

    Attributes:
        user_id: ID del jugador que deposita.
        slot: Slot del inventario a depositar.
        quantity: Cantidad a depositar.
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
