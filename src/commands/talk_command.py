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

    def is_clan_command(self) -> bool:
        """Determina si el mensaje es un comando de clan.

        Returns:
            True si el mensaje es un comando de clan, False en caso contrario.
        """
        message_upper = self.message.upper().strip()
        clan_commands = [
            "/CREARCLAN",
            "/INVITARCLAN",
            "/ACEPTARCLAN",
            "/RECHAZARCLAN",
            "/SALIRCLAN",
            "/EXPULSARCLAN",
            "/CLAN",
        ]
        return any(message_upper.startswith(cmd) for cmd in clan_commands)

    def parse_clan_command(self) -> tuple[str, list[str]] | None:
        """Parsea un comando de clan del mensaje.

        Returns:
            Tupla (comando, argumentos) o None si no es un comando válido.
            Ejemplo: ("CREARCLAN", ["MiClan", "Descripción opcional"])
        """
        if not self.is_clan_command():
            return None

        parts = self.message.strip().split()
        if not parts:
            return None

        command = parts[0].upper().replace("/", "")
        args = parts[1:] if len(parts) > 1 else []

        return (command, args)
