"""Comando para mensaje susurrado (chat privado)."""

from dataclasses import dataclass
from time import time

from src.commands.base import Command


@dataclass
class WhisperCommand(Command):
    """Comando para susurro (solo datos).

    Attributes:
        user_id: ID del usuario que envía el susurro.
        receiver: Nombre del usuario destinatario.
        message: Mensaje privado.
        timestamp: Timestamp del comando.
    """

    user_id: int
    receiver: str
    message: str
    timestamp: float | None = None

    def __post_init__(self) -> None:
        """Inicializa timestamp si no se proporciona."""
        if self.timestamp is None:
            self.timestamp = time()
