"""Comando para transferir el liderazgo de un clan."""

from dataclasses import dataclass

from src.commands.base import Command


@dataclass
class TransferClanLeadershipCommand(Command):
    """Comando para transferir el liderazgo de un clan.

    Attributes:
        new_leader_username: Nombre de usuario del nuevo líder.
    """

    new_leader_username: str
