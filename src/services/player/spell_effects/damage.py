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
        if not ctx.target_player_id or not ctx.target_player_stats or not ctx.player_repo:
            return SpellEffectResult(success=False)

        stats = ctx.target_player_stats
        current_hp = stats.get("min_hp", 0)
        new_hp = max(0, current_hp - ctx.total_amount)
        stats["min_hp"] = new_hp

        await ctx.player_repo.set_stats(user_id=ctx.target_player_id, **stats)

        # Notificar al jugador objetivo (si no es auto-cast)
        if not ctx.is_self_cast:
            target_sender = await ctx.get_target_message_sender()
            if target_sender:
                await target_sender.send_update_user_stats(**stats)
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

        # Obtener stats del caster
        caster_stats = await ctx.player_repo.get_stats(ctx.user_id)
        if not caster_stats:
            return SpellEffectResult(success=False)

        current_caster_hp = caster_stats.get("min_hp", 0)
        max_caster_hp = caster_stats.get("max_hp", 100)

        # Transferir HP drenado al caster (no exceder max_hp)
        new_caster_hp = min(max_caster_hp, current_caster_hp + ctx.total_amount)
        caster_stats["min_hp"] = new_caster_hp

        # Guardar stats del caster
        await ctx.player_repo.set_stats(user_id=ctx.user_id, **caster_stats)
        await ctx.message_sender.send_update_user_stats(**caster_stats)

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
