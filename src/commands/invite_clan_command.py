"""Comando para invitar a un jugador a un clan."""

from dataclasses import dataclass

from src.commands.base import Command


@dataclass
class InviteClanCommand(Command):
    """Comando para invitar a un jugador a un clan.

    Attributes:
        target_username: Nombre de usuario del jugador a invitar.
    """

    target_username: str
