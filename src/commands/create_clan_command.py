"""Comando para crear un clan."""

from dataclasses import dataclass

from src.commands.base import Command


@dataclass
class CreateClanCommand(Command):
    """Comando para crear un clan.

    Attributes:
        clan_name: Nombre del clan a crear.
        description: Descripción opcional del clan.
    """

    clan_name: str
    description: str = ""
