"""Efectos de curación de hechizos."""

from __future__ import annotations

import logging

from src.services.player.spell_effects.base import SpellContext, SpellEffect, SpellEffectResult

logger = logging.getLogger(__name__)

# Porcentaje de HP al revivir (50%)
REVIVE_HP_PERCENTAGE = 0.5


class HealEffect(SpellEffect):
    """Efecto de curación de HP."""

    def can_apply(self, ctx: SpellContext) -> bool:
        """Verifica si el hechizo cura HP."""
        return ctx.spell_data.get("heals_hp", False)

    async def apply_to_npc(self, ctx: SpellContext) -> SpellEffectResult:
        """Aplica curación a un NPC."""
        if not ctx.target_npc or not ctx.npc_repo:
            return SpellEffectResult(success=False)

        npc = ctx.target_npc
        old_hp = npc.hp
        npc.hp = min(npc.hp + ctx.total_amount, npc.max_hp)
        healing_amount = npc.hp - old_hp

        # Actualizar HP en Redis
        await ctx.npc_repo.update_npc_hp(npc.instance_id, npc.hp)

        logger.info(
            "NPC %s curado por %d HP (HP: %d/%d) con hechizo %s",
            npc.name,
            healing_amount,
            npc.hp,
            npc.max_hp,
            ctx.spell_name,
        )

        return SpellEffectResult(
            success=True,
            data={"healing_amount": healing_amount, "new_hp": npc.hp},
        )

    async def apply_to_player(self, ctx: SpellContext) -> SpellEffectResult:
        """Aplica curación a un jugador."""
        if not ctx.target_player_id or not ctx.target_player_stats or not ctx.player_repo:
            return SpellEffectResult(success=False)

        stats = ctx.target_player_stats
        current_hp = stats.get("min_hp", 0)
        max_hp = stats.get("max_hp", 100)
        new_hp = min(current_hp + ctx.total_amount, max_hp)
        healing_amount = new_hp - current_hp

        stats["min_hp"] = new_hp
        await ctx.player_repo.set_stats(user_id=ctx.target_player_id, **stats)

        # Notificar al jugador objetivo
        target_sender = await ctx.get_target_message_sender()
        if target_sender:
            await target_sender.send_update_user_stats(**stats)
            if healing_amount > 0:
                msg = (
                    f"Te has curado {healing_amount} HP."
                    if ctx.is_self_cast
                    else f"Te han curado {healing_amount} HP."
                )
                await target_sender.send_console_msg(msg)

        logger.info(
            "Jugador user_id %d curado por %d HP (HP: %d/%d) con hechizo %s",
            ctx.target_player_id,
            healing_amount,
            new_hp,
            max_hp,
            ctx.spell_name,
        )

        return SpellEffectResult(
            success=True,
            data={"healing_amount": healing_amount, "new_hp": new_hp},
        )


class ReviveEffect(SpellEffect):
    """Efecto de resucitación."""

    def can_apply(self, ctx: SpellContext) -> bool:
        """Verifica si el hechizo resucita."""
        return ctx.spell_data.get("revives", False)

    async def apply_to_npc(self, ctx: SpellContext) -> SpellEffectResult:
        """No se puede resucitar NPCs."""
        return SpellEffectResult(success=False, message="No se puede resucitar NPCs")

    async def apply_to_player(self, ctx: SpellContext) -> SpellEffectResult:
        """Aplica resucitación a un jugador."""
        if not ctx.target_player_id or not ctx.player_repo:
            return SpellEffectResult(success=False, message="No hay objetivo válido para resucitar")

        # No puede resucitarse a sí mismo
        if ctx.target_player_id == ctx.user_id:
            if ctx.message_sender:
                await ctx.message_sender.send_console_msg("No puedes resucitarte a ti mismo.")
            return SpellEffectResult(success=False, stop_processing=True)

        # Obtener stats del target
        target_stats = await ctx.player_repo.get_stats(ctx.target_player_id)
        if not target_stats:
            if ctx.message_sender:
                await ctx.message_sender.send_console_msg("Objetivo inválido.")
            return SpellEffectResult(success=False, stop_processing=True)

        current_hp = target_stats.get("min_hp", 0)
        max_hp = target_stats.get("max_hp", 100)

        # Verificar si el jugador está muerto
        if current_hp > 0:
            if ctx.message_sender:
                await ctx.message_sender.send_console_msg(f"{ctx.target_name} no está muerto.")
            return SpellEffectResult(success=False, stop_processing=True)

        # Revivir con HP parcial
        revive_hp = int(max_hp * REVIVE_HP_PERCENTAGE)
        target_stats["min_hp"] = revive_hp
        await ctx.player_repo.set_stats(user_id=ctx.target_player_id, **target_stats)

        # Notificar al caster
        if ctx.message_sender:
            await ctx.message_sender.send_console_msg(f"Has resucitado a {ctx.target_name}.")

        # Notificar al jugador revivido
        target_sender = await ctx.get_target_message_sender()
        if target_sender:
            await target_sender.send_update_user_stats(**target_stats)
            await target_sender.send_console_msg(
                f"{ctx.spell_name} te ha resucitado. Tienes {revive_hp}/{max_hp} HP."
            )

        logger.info(
            "user_id %d resucitado por user_id %d con %s (HP: %d/%d)",
            ctx.target_player_id,
            ctx.user_id,
            ctx.spell_name,
            revive_hp,
            max_hp,
        )

        return SpellEffectResult(success=True, stop_processing=True)
