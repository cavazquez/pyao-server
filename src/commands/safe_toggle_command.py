"""Comando para togglear modo seguro (anti-PvP)."""

from dataclasses import dataclass

from src.commands.base import Command


@dataclass
class SafeToggleCommand(Command):
    """Comando para togglear el modo seguro del jugador.

    Attributes:
        user_id: ID del usuario.
    """

    user_id: int
