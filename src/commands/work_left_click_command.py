"""Comando de trabajo con click (pesca, tala, minería)."""

from dataclasses import dataclass
from time import time

from src.commands.base import Command


@dataclass
class WorkLeftClickCommand(Command):
    """Comando de trabajo con click (solo datos).

    Attributes:
        user_id: ID del jugador que trabaja.
        map_id: ID del mapa donde está trabajando.
        target_x: Coordenada X objetivo del click.
        target_y: Coordenada Y objetivo del click.
        skill_type: Tipo de habilidad (9=Talar, 12=Pesca, 13=Minería).
        timestamp: Timestamp del comando.
    """

    user_id: int
    map_id: int
    target_x: int
    target_y: int
    skill_type: int
    timestamp: float | None = None

    def __post_init__(self) -> None:
        """Inicializa timestamp si no se proporciona."""
        if self.timestamp is None:
            self.timestamp = time()
