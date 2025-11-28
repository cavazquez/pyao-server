"""Comando para degradar a un miembro de un clan."""

from dataclasses import dataclass

from src.commands.base import Command


@dataclass
class DemoteClanMemberCommand(Command):
    """Comando para degradar a un miembro de un clan.

    Attributes:
        target_username: Nombre de usuario del miembro a degradar.
    """

    target_username: str
