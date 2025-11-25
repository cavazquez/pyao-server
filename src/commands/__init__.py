"""Sistema de comandos usando Command Pattern.

Este módulo exporta las clases base del Command Pattern.

Para comandos específicos, usa importaciones directas:
    from src.commands.attack_command import AttackCommand
"""

from src.commands.base import Command, CommandHandler, CommandResult

__all__ = [
    "Command",
    "CommandHandler",
    "CommandResult",
]
