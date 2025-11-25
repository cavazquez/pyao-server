"""Comando de extraer item del banco."""

from dataclasses import dataclass
from time import time

from src.commands.base import Command


@dataclass
class BankExtractCommand(Command):
    """Comando de extraer item del banco (solo datos).

    Attributes:
        user_id: ID del jugador que extrae.
        slot: Slot del banco a extraer.
        quantity: Cantidad a extraer.
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
