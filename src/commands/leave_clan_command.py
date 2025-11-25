"""Comando para abandonar un clan."""

from dataclasses import dataclass

from src.commands.base import Command


@dataclass
class LeaveClanCommand(Command):
    """Comando para abandonar un clan."""
