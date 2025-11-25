"""Handlers de comandos usando Command Pattern.

Este módulo exporta las clases base del Command Pattern.

Para handlers específicos, usa importaciones directas:
    from src.command_handlers.attack_handler import AttackCommandHandler
"""

from src.commands.base import CommandHandler

__all__ = [
    "CommandHandler",
]
