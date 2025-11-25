"""Comando para mensaje de chat."""

from dataclasses import dataclass
from time import time

from src.commands.base import Command


@dataclass
class TalkCommand(Command):
    """Comando para mensaje de chat (solo datos).

    Attributes:
        user_id: ID del usuario que envía el mensaje.
        message: Mensaje de chat.
        timestamp: Timestamp del comando.
    """

    user_id: int
    message: str
    timestamp: float | None = None

    def __post_init__(self) -> None:
        """Inicializa timestamp si no se proporciona."""
        if self.timestamp is None:
            self.timestamp = time()

    def is_metrics_command(self) -> bool:
        """Determina si el mensaje es el comando /METRICS.

        Returns:
            True si el mensaje es el comando /METRICS, False en caso contrario.
        """
        return self.message.upper().startswith("/METRICS")
