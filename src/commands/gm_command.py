"""Comando para comandos de Game Master."""

from dataclasses import dataclass
from time import time

from src.commands.base import Command


@dataclass
class GMCommand(Command):
    """Comando para comandos de Game Master (solo datos).

    Attributes:
        user_id: ID del jugador que ejecuta el comando.
        subcommand: Subcomando GM (ej: WARP_CHAR).
        username: Nombre del usuario objetivo (o "YO" para teletransportarse a sí mismo).
        map_id: ID del mapa destino.
        x: Coordenada X destino.
        y: Coordenada Y destino.
        timestamp: Timestamp del comando.
    """

    user_id: int
    subcommand: int
    username: str
    map_id: int
    x: int
    y: int
    timestamp: float | None = None

    def __post_init__(self) -> None:
        """Inicializa timestamp si no se proporciona."""
        if self.timestamp is None:
            self.timestamp = time()

    def is_self_teleport(self) -> bool:
        """Determina si el comando es para teletransportarse a sí mismo.

        Returns:
            True si username está vacío, es "YO" o "余", False en caso contrario.
        """
        return not self.username or self.username.upper() == "YO" or self.username == "余"
