"""Registry de efectos de hechizos."""

from __future__ import annotations

from src.services.player.spell_effects.base import (  # noqa: TC001
    SpellContext,
    SpellEffect,
    SpellEffectResult,
)
from src.services.player.spell_effects.buffs import (
    AgilityBuffEffect,
    AgilityDebuffEffect,
    InvisibilityEffect,
    MorphEffect,
    RemoveInvisibilityEffect,
    StrengthBuffEffect,
    StrengthDebuffEffect,
)
from src.services.player.spell_effects.damage import DamageEffect, DrainEffect
from src.services.player.spell_effects.healing import HealEffect, ReviveEffect
from src.services.player.spell_effects.special import HungerEffect, SummonEffect, WarpPetEffect
from src.services.player.spell_effects.status import (
    BlindEffect,
    CurePoisonEffect,
    DumbEffect,
    ImmobilizeEffect,
    ParalysisEffect,
    PoisonEffect,
    RemoveDumbEffect,
    RemoveParalysisEffect,
)


class SpellEffectRegistry:
    """Registry que gestiona todos los efectos de hechizos.

    Los efectos se procesan en orden de prioridad:
    1. Efectos especiales que detienen procesamiento (revive, summon)
    2. Efectos de curación/daño
    3. Efectos que remueven estados (cure poison, remove paralysis)
    4. Efectos que aplican estados (poison, paralysis, etc.)
    5. Efectos de buffs/debuffs
    6. Efectos especiales (drain, morph, hunger, warp pet)
    """

    def __init__(self) -> None:
        """Inicializa el registry con todos los efectos."""
        # Orden de prioridad de efectos
        self._effects: list[SpellEffect] = [
            # Fase 1: Efectos que pueden detener procesamiento
            ReviveEffect(),
            SummonEffect(),
            # Fase 2: Curación/Daño
            HealEffect(),
            DamageEffect(),
            # Fase 3: Remover estados (antes de aplicar nuevos)
            CurePoisonEffect(),
            RemoveParalysisEffect(),
            RemoveDumbEffect(),
            RemoveInvisibilityEffect(),
            # Fase 4: Aplicar estados
            PoisonEffect(),
            ParalysisEffect(),
            ImmobilizeEffect(),
            BlindEffect(),
            DumbEffect(),
            # Fase 5: Buffs/Debuffs
            InvisibilityEffect(),
            StrengthBuffEffect(),
            StrengthDebuffEffect(),
            AgilityBuffEffect(),
            AgilityDebuffEffect(),
            # Fase 6: Efectos especiales
            DrainEffect(),
            MorphEffect(),
            HungerEffect(),
            WarpPetEffect(),
        ]

    async def apply_effects(self, ctx: SpellContext) -> list[SpellEffectResult]:
        """Aplica todos los efectos aplicables al contexto.

        Args:
            ctx: Contexto del hechizo.

        Returns:
            Lista de resultados de cada efecto aplicado.
        """
        results: list[SpellEffectResult] = []

        for effect in self._effects:
            if effect.can_apply(ctx):
                result = await effect.apply(ctx)
                results.append(result)

                # Si el efecto indica detener, no procesar más
                if result.stop_processing:
                    break

        return results

    def get_applicable_effects(self, ctx: SpellContext) -> list[SpellEffect]:
        """Obtiene la lista de efectos que aplican al contexto.

        Args:
            ctx: Contexto del hechizo.

        Returns:
            Lista de efectos aplicables.
        """
        return [effect for effect in self._effects if effect.can_apply(ctx)]


# Singleton del registry
_registry: SpellEffectRegistry | None = None


def get_spell_effect_registry() -> SpellEffectRegistry:
    """Obtiene el singleton del registry de efectos."""
    global _registry  # noqa: PLW0603
    if _registry is None:
        _registry = SpellEffectRegistry()
    return _registry
