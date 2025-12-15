"""Efectos de daño de hechizos."""

from __future__ import annotations

import logging

from src.services.player.spell_effects.base import SpellContext, SpellEffect, SpellEffectResult

logger = logging.getLogger(__name__)


class DamageEffect(SpellEffect):
    """Efecto de daño directo."""

    def can_apply(self, ctx: SpellContext) -> bool:
        """Verifica si el hechizo hace daño (y no cura)."""
        if ctx.spell_data.get("heals_hp", False):
            return False
        min_damage = ctx.spell_data.get("min_damage", 0)
        max_damage = ctx.spell_data.get("max_damage", 0)
        return min_damage > 0 or max_damage > 0

    async def apply_to_npc(self, ctx: SpellContext) -> SpellEffectResult:
        """Aplica daño a un NPC."""
        if not ctx.target_npc or not ctx.npc_repo:
            return SpellEffectResult(success=False)

        npc = ctx.target_npc
        npc.hp = max(0, npc.hp - ctx.total_amount)
        ctx.npc_died = npc.hp <= 0

        # Actualizar HP en Redis (si no murió)
        if not ctx.npc_died:
            await ctx.npc_repo.update_npc_hp(npc.instance_id, npc.hp)

        logger.info(
            "NPC %s recibió %d de daño con hechizo %s (HP: %d/%d)",
            npc.name,
            ctx.total_amount,
            ctx.spell_name,
            npc.hp,
            npc.max_hp,
        )

        return SpellEffectResult(
            success=True,
            data={"damage": ctx.total_amount, "npc_died": ctx.npc_died},
        )

    async def apply_to_player(self, ctx: SpellContext) -> SpellEffectResult:
        """Aplica daño a un jugador."""
        if not ctx.target_player_id or not ctx.player_repo:
            return SpellEffectResult(success=False)

        # Obtener HP actual y calcular nuevo HP
        current_hp = await ctx.player_repo.get_current_hp(ctx.target_player_id)
        new_hp = max(0, current_hp - ctx.total_amount)

        # Actualizar HP
        await ctx.player_repo.update_hp(ctx.target_player_id, new_hp)

        # Obtener stats completos para enviar actualización
        stats = await ctx.player_repo.get_player_stats(ctx.target_player_id)

        # Notificar al jugador objetivo (si no es auto-cast)
        if not ctx.is_self_cast:
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
                await target_sender.send_console_msg(
                    f"{ctx.spell_name} te ha causado {ctx.total_amount} de daño."
                )

        player_died = new_hp <= 0
        if player_died:
            logger.info(
                "Jugador user_id %d murió por hechizo %s (daño: %d)",
                ctx.target_player_id,
                ctx.spell_name,
                ctx.total_amount,
            )

        return SpellEffectResult(
            success=True,
            data={"damage": ctx.total_amount, "new_hp": new_hp, "player_died": player_died},
        )


class DrainEffect(SpellEffect):
    """Efecto de drenar HP (daño + curación al caster)."""

    # ID del hechizo Drenar
    SPELL_ID_DRAIN = 45

    def can_apply(self, ctx: SpellContext) -> bool:
        """Verifica si es el hechizo drenar."""
        return ctx.spell_id == self.SPELL_ID_DRAIN and ctx.total_amount > 0

    async def apply_to_npc(self, ctx: SpellContext) -> SpellEffectResult:
        """Drena HP de un NPC al caster."""
        if not ctx.target_npc or ctx.npc_died:
            return SpellEffectResult(success=False)

        return await self._drain_to_caster(ctx)

    async def apply_to_player(self, ctx: SpellContext) -> SpellEffectResult:
        """Drena HP de un jugador al caster."""
        if not ctx.target_player_id:
            return SpellEffectResult(success=False)

        return await self._drain_to_caster(ctx)

    async def _drain_to_caster(self, ctx: SpellContext) -> SpellEffectResult:
        """Transfiere HP drenado al caster."""
        if not ctx.player_repo or not ctx.message_sender:
            return SpellEffectResult(success=False)

        # Obtener HP del caster
        current_caster_hp = await ctx.player_repo.get_current_hp(ctx.user_id)
        max_caster_hp = await ctx.player_repo.get_max_hp(ctx.user_id)

        # Transferir HP drenado al caster (no exceder max_hp)
        new_caster_hp = min(max_caster_hp, current_caster_hp + ctx.total_amount)

        # Actualizar HP del caster
        await ctx.player_repo.update_hp(ctx.user_id, new_caster_hp)

        # Obtener stats completos para enviar actualización
        caster_stats = await ctx.player_repo.get_player_stats(ctx.user_id)
        if caster_stats and ctx.message_sender:
            await ctx.message_sender.send_update_user_stats(
                max_hp=caster_stats.max_hp,
                min_hp=new_caster_hp,
                max_mana=caster_stats.max_mana,
                min_mana=caster_stats.min_mana,
                max_sta=caster_stats.max_sta,
                min_sta=caster_stats.min_sta,
                gold=caster_stats.gold,
                level=caster_stats.level,
                elu=caster_stats.elu,
                experience=caster_stats.experience,
            )

        hp_gained = new_caster_hp - current_caster_hp
        if hp_gained > 0:
            await ctx.message_sender.send_console_msg(f"Has drenado {hp_gained} HP del objetivo.")

        logger.info(
            "user_id %d drenó %d HP de %s (HP caster: %d/%d)",
            ctx.user_id,
            ctx.total_amount,
            ctx.target_name,
            new_caster_hp,
            max_caster_hp,
        )

        return SpellEffectResult(success=True, data={"hp_gained": hp_gained})
