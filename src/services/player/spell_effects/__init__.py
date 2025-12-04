"""Sistema de efectos de hechizos (Strategy Pattern)."""

from src.services.player.spell_effects.base import (
    SpellContext,
    SpellEffect,
    SpellEffectResult,
)
from src.services.player.spell_effects.registry import (
    SpellEffectRegistry,
    get_spell_effect_registry,
)

__all__ = [
    "SpellContext",
    "SpellEffect",
    "SpellEffectRegistry",
    "SpellEffectResult",
    "get_spell_effect_registry",
]
