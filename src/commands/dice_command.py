"""Comando para tirada de dados."""

from dataclasses import dataclass
from time import time

from src.commands.base import Command


@dataclass
class DiceCommand(Command):
    """Comando para tirada de dados.

    Attributes:
        min_value: Valor mínimo para los dados.
        max_value: Valor máximo para los dados.
        timestamp: Timestamp del comando.
    """

    min_value: int
    max_value: int
    timestamp: float | None = None

    def __post_init__(self) -> None:
        """Inicializa timestamp si no se proporciona."""
        if self.timestamp is None:
            self.timestamp = time()
