"""Comando para solicitar atributos del jugador."""

from dataclasses import dataclass
from time import time

from src.commands.base import Command


@dataclass
class RequestAttributesCommand(Command):
    """Comando para solicitar atributos del jugador.

    Attributes:
        user_id: ID del usuario (None si es desde sesión de creación de personaje).
        dice_attributes: Atributos desde sesión (creación de personaje),
            None si se obtienen del repositorio.
        timestamp: Timestamp del comando.
    """

    user_id: int | None
    dice_attributes: dict[str, int] | None = None
    timestamp: float | None = None

    def __post_init__(self) -> None:
        """Inicializa timestamp si no se proporciona."""
        if self.timestamp is None:
            self.timestamp = time()
