"""Comando para promover a un miembro de un clan."""

from dataclasses import dataclass

from src.commands.base import Command


@dataclass
class PromoteClanMemberCommand(Command):
    """Comando para promover a un miembro de un clan.

    Attributes:
        target_username: Nombre de usuario del miembro a promover.
    """

    target_username: str
