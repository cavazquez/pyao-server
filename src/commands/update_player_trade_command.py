"""Comando para actualizar el estado de un comercio entre jugadores."""

from dataclasses import dataclass
from enum import StrEnum

from src.commands.base import Command


class TradeUpdateAction(StrEnum):
    """Acciones posibles dentro de una sesión de comercio."""

    CANCEL = "cancel"
    CONFIRM = "confirm"
    READY = "ready"
    REJECT = "reject"


@dataclass
class UpdatePlayerTradeCommand(Command):
    """Comando enviado por tasks de comercio."""

    user_id: int
    action: TradeUpdateAction
