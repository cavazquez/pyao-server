"""Comando para iniciar comercio entre jugadores."""

from dataclasses import dataclass

from src.commands.base import Command


@dataclass
class StartPlayerTradeCommand(Command):
    """Datos necesarios para iniciar un comercio entre jugadores."""

    initiator_id: int
    target_username: str
