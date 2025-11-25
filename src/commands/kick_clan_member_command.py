"""Comando para expulsar a un miembro de un clan."""

from dataclasses import dataclass

from src.commands.base import Command


@dataclass
class KickClanMemberCommand(Command):
    """Comando para expulsar a un miembro de un clan.

    Attributes:
        target_username: Nombre de usuario del miembro a expulsar.
    """

    target_username: str
