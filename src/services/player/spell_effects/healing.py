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
        if not ctx.target_player_id or not ctx.player_repo:
            return SpellEffectResult(success=False)

        # Obtener stats del jugador
        current_hp = await ctx.player_repo.get_current_hp(ctx.target_player_id)
        max_hp = await ctx.player_repo.get_max_hp(ctx.target_player_id)
        new_hp = min(current_hp + ctx.total_amount, max_hp)
        healing_amount = new_hp - current_hp

        # Actualizar HP
        await ctx.player_repo.update_hp(ctx.target_player_id, new_hp)

        # Obtener stats completos para enviar actualización
        stats = await ctx.player_repo.get_player_stats(ctx.target_player_id)

        # Notificar al jugador objetivo
        target_sender = await ctx.get_target_message_sender()
        if target_sender and stats:
            await target_sender.send_update_user_stats(
                max_hp=stats.max_hp,
                min_hp=new_hp,
                max_mana=stats.max_mana,
                min_mana=stats.min_mana,
                max_sta=stats.max_sta,
                min_sta=stats.min_sta,
                gold=stats.gold,
                level=stats.level,
                elu=stats.elu,
                experience=stats.experience,
            )
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

        # Verificar si el jugador está muerto
        if await ctx.player_repo.is_alive(ctx.target_player_id):
            if ctx.message_sender:
                await ctx.message_sender.send_console_msg(f"{ctx.target_name} no está muerto.")
            return SpellEffectResult(success=False, stop_processing=True)

        # Obtener max_hp para calcular revive_hp
        max_hp = await ctx.player_repo.get_max_hp(ctx.target_player_id)
        revive_hp = int(max_hp * REVIVE_HP_PERCENTAGE)

        # Actualizar HP
        await ctx.player_repo.update_hp(ctx.target_player_id, revive_hp)

        # Obtener stats completos para enviar actualización
        target_stats = await ctx.player_repo.get_player_stats(ctx.target_player_id)

        # Notificar al caster
        if ctx.message_sender:
            await ctx.message_sender.send_console_msg(f"Has resucitado a {ctx.target_name}.")

        # Notificar al jugador revivido
        target_sender = await ctx.get_target_message_sender()
        if target_sender and target_stats:
            await target_sender.send_update_user_stats(
                max_hp=target_stats.max_hp,
                min_hp=revive_hp,
                max_mana=target_stats.max_mana,
                min_mana=target_stats.min_mana,
                max_sta=target_stats.max_sta,
                min_sta=target_stats.min_sta,
                gold=target_stats.gold,
                level=target_stats.level,
                elu=target_stats.elu,
                experience=target_stats.experience,
            )
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
