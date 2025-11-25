"""Comando para aceptar una invitación a un clan."""

from dataclasses import dataclass

from src.commands.base import Command


@dataclass
class AcceptClanCommand(Command):
    """Comando para aceptar una invitación a un clan."""
