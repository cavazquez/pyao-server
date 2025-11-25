"""Comando para solicitar detalles del clan."""

from src.commands.base import Command


class RequestClanDetailsCommand(Command):
    """Comando para solicitar detalles del clan.

    Se envía cuando el jugador hace click en el botón del clan
    para abrir el menú y ver la información del clan.
    """
