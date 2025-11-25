"""Handlers de comandos usando Command Pattern."""

from src.command_handlers.attack_handler import AttackCommandHandler
from src.command_handlers.cast_spell_handler import CastSpellCommandHandler
from src.command_handlers.use_item_handler import UseItemCommandHandler
from src.command_handlers.walk_handler import WalkCommandHandler

__all__ = [
    "AttackCommandHandler",
    "CastSpellCommandHandler",
    "UseItemCommandHandler",
    "WalkCommandHandler",
]
