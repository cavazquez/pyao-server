"""Comando para rechazar una invitación a un clan."""

from dataclasses import dataclass

from src.commands.base import Command


@dataclass
class RejectClanCommand(Command):
    """Comando para rechazar una invitación a un clan."""
