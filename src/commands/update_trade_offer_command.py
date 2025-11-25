"""Comando para actualizar la oferta de comercio."""

from dataclasses import dataclass

from src.commands.base import Command


@dataclass
class UpdateTradeOfferCommand(Command):
    """Representa un cambio en la oferta del jugador."""

    user_id: int
    slot: int
    quantity: int
