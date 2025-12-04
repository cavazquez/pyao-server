"""Efectos de estado de hechizos (veneno, parálisis, ceguera, etc.)."""

from __future__ import annotations

import logging
import time

from src.services.player.spell_effects.base import SpellContext, SpellEffect, SpellEffectResult

logger = logging.getLogger(__name__)

# Duraciones de efectos (segundos)
POISON_DURATION_SECONDS = 30.0
IMMOBILIZATION_DURATION_SECONDS = 30.0
BLINDNESS_DURATION_SECONDS = 10.0
DUMBNESS_DURATION_SECONDS = 30.0
INVISIBILITY_DURATION_SECONDS = 60.0
PARALYSIS_DURATION_SECONDS = 10.0


class PoisonEffect(SpellEffect):
    """Efecto de envenenamiento."""

    def can_apply(self, ctx: SpellContext) -> bool:
        """Verifica si el hechizo envenena."""
        return ctx.spell_data.get("poisons", False)

    async def apply_to_npc(self, ctx: SpellContext) -> SpellEffectResult:
        """Aplica envenenamiento a un NPC."""
        if not ctx.target_npc or ctx.npc_died or not ctx.npc_repo:
            return SpellEffectResult(success=False)

        npc = ctx.target_npc
        poisoned_until = time.time() + POISON_DURATION_SECONDS
        npc.poisoned_until = poisoned_until
        npc.poisoned_by_user_id = ctx.user_id

        await ctx.npc_repo.update_npc_poisoned_until(
            npc.instance_id, poisoned_until, poisoned_by_user_id=ctx.user_id
        )

        logger.info(
            "NPC %s envenenado por user_id %d con hechizo %s (duración: %.1fs)",
            npc.name,
            ctx.user_id,
            ctx.spell_name,
            POISON_DURATION_SECONDS,
        )

        return SpellEffectResult(success=True)

    async def apply_to_player(self, ctx: SpellContext) -> SpellEffectResult:
        """Aplica envenenamiento a un jugador."""
        if not ctx.target_player_id or not ctx.player_repo:
            return SpellEffectResult(success=False)

        poisoned_until = time.time() + POISON_DURATION_SECONDS
        await ctx.player_repo.update_poisoned_until(ctx.target_player_id, poisoned_until)

        logger.info(
            "Jugador user_id %d envenenado por hechizo %s (duración: %.1fs)",
            ctx.target_player_id,
            ctx.spell_name,
            POISON_DURATION_SECONDS,
        )

        # Notificar
        target_sender = await ctx.get_target_message_sender()
        if target_sender:
            msg = "Te has envenenado." if ctx.is_self_cast else "Has sido envenenado."
            await target_sender.send_console_msg(msg)

        return SpellEffectResult(success=True)


class CurePoisonEffect(SpellEffect):
    """Efecto de curar veneno."""

    def can_apply(self, ctx: SpellContext) -> bool:
        """Verifica si el hechizo cura veneno."""
        return ctx.spell_data.get("cures_poison", False)

    async def apply_to_npc(self, ctx: SpellContext) -> SpellEffectResult:
        """Cura veneno de un NPC."""
        if not ctx.target_npc or ctx.npc_died or not ctx.npc_repo:
            return SpellEffectResult(success=False)

        await ctx.npc_repo.update_npc_poisoned_until(ctx.target_npc.instance_id, 0.0)
        logger.info("Veneno removido de NPC %s por hechizo %s", ctx.target_npc.name, ctx.spell_name)
        return SpellEffectResult(success=True)

    async def apply_to_player(self, ctx: SpellContext) -> SpellEffectResult:
        """Cura veneno de un jugador."""
        if not ctx.target_player_id or not ctx.player_repo:
            return SpellEffectResult(success=False)

        await ctx.player_repo.update_poisoned_until(ctx.target_player_id, 0.0)
        logger.info(
            "Veneno removido de user_id %d por hechizo %s", ctx.target_player_id, ctx.spell_name
        )

        target_sender = await ctx.get_target_message_sender()
        if target_sender:
            msg = (
                "Te has curado del envenenamiento."
                if ctx.is_self_cast
                else "Te han curado del envenenamiento."
            )
            await target_sender.send_console_msg(msg)

        return SpellEffectResult(success=True)


class ParalysisEffect(SpellEffect):
    """Efecto de parálisis (para NPCs)."""

    SPELL_ID_PARALYZE = 9
    SPELL_TYPE_STATUS = 2

    def can_apply(self, ctx: SpellContext) -> bool:
        """Verifica si el hechizo paraliza."""
        spell_type = ctx.spell_data.get("type", 1)
        spell_name_lower = ctx.spell_name.lower()
        return spell_type == self.SPELL_TYPE_STATUS and (
            "paralizar" in spell_name_lower or ctx.spell_id == self.SPELL_ID_PARALYZE
        )

    async def apply_to_npc(self, ctx: SpellContext) -> SpellEffectResult:
        """Aplica parálisis a un NPC."""
        if not ctx.target_npc or ctx.npc_died or not ctx.npc_repo:
            return SpellEffectResult(success=False)

        npc = ctx.target_npc
        paralyzed_until = time.time() + PARALYSIS_DURATION_SECONDS
        npc.paralyzed_until = paralyzed_until

        await ctx.npc_repo.update_npc_paralyzed_until(npc.instance_id, paralyzed_until)

        logger.info("NPC %s paralizado (duración: %.1fs)", npc.name, PARALYSIS_DURATION_SECONDS)

        return SpellEffectResult(success=True)

    async def apply_to_player(self, ctx: SpellContext) -> SpellEffectResult:
        """La parálisis para jugadores se maneja como inmovilización."""
        return SpellEffectResult(success=False)


class RemoveParalysisEffect(SpellEffect):
    """Efecto de remover parálisis/inmovilización."""

    def can_apply(self, ctx: SpellContext) -> bool:
        """Verifica si el hechizo remueve parálisis."""
        return ctx.spell_data.get("removes_paralysis", False)

    async def apply_to_npc(self, ctx: SpellContext) -> SpellEffectResult:
        """Remueve parálisis de un NPC."""
        if not ctx.target_npc or ctx.npc_died or not ctx.npc_repo:
            return SpellEffectResult(success=False)

        await ctx.npc_repo.update_npc_paralyzed_until(ctx.target_npc.instance_id, 0.0)
        logger.info(
            "Parálisis removida de NPC %s por hechizo %s", ctx.target_npc.name, ctx.spell_name
        )
        return SpellEffectResult(success=True)

    async def apply_to_player(self, ctx: SpellContext) -> SpellEffectResult:
        """Remueve inmovilización de un jugador."""
        if not ctx.target_player_id or not ctx.player_repo:
            return SpellEffectResult(success=False)

        await ctx.player_repo.update_immobilized_until(ctx.target_player_id, 0.0)
        logger.info(
            "Inmovilización removida de user_id %d por hechizo %s",
            ctx.target_player_id,
            ctx.spell_name,
        )

        target_sender = await ctx.get_target_message_sender()
        if target_sender:
            msg = (
                "Te has devuelto la movilidad."
                if ctx.is_self_cast
                else "Te han devuelto la movilidad."
            )
            await target_sender.send_console_msg(msg)

        return SpellEffectResult(success=True)


class ImmobilizeEffect(SpellEffect):
    """Efecto de inmovilización (para jugadores)."""

    def can_apply(self, ctx: SpellContext) -> bool:
        """Verifica si el hechizo inmoviliza."""
        return ctx.spell_data.get("immobilizes", False)

    async def apply_to_npc(self, ctx: SpellContext) -> SpellEffectResult:
        """NPCs usan parálisis, no inmovilización."""
        return SpellEffectResult(success=False)

    async def apply_to_player(self, ctx: SpellContext) -> SpellEffectResult:
        """Aplica inmovilización a un jugador."""
        if not ctx.target_player_id or not ctx.player_repo:
            return SpellEffectResult(success=False)

        immobilized_until = time.time() + IMMOBILIZATION_DURATION_SECONDS
        await ctx.player_repo.update_immobilized_until(ctx.target_player_id, immobilized_until)

        logger.info(
            "Jugador user_id %d inmovilizado por hechizo %s (duración: %.1fs)",
            ctx.target_player_id,
            ctx.spell_name,
            IMMOBILIZATION_DURATION_SECONDS,
        )

        target_sender = await ctx.get_target_message_sender()
        if target_sender:
            msg = "Te has inmovilizado." if ctx.is_self_cast else "Has sido inmovilizado."
            await target_sender.send_console_msg(msg)

        return SpellEffectResult(success=True)


class BlindEffect(SpellEffect):
    """Efecto de ceguera."""

    def can_apply(self, ctx: SpellContext) -> bool:
        """Verifica si el hechizo ciega."""
        return ctx.spell_data.get("blinds", False)

    async def apply_to_npc(self, ctx: SpellContext) -> SpellEffectResult:
        """NPCs no pueden ser cegados."""
        return SpellEffectResult(success=False)

    async def apply_to_player(self, ctx: SpellContext) -> SpellEffectResult:
        """Aplica ceguera a un jugador."""
        if not ctx.target_player_id or not ctx.player_repo:
            return SpellEffectResult(success=False)

        blinded_until = time.time() + BLINDNESS_DURATION_SECONDS
        await ctx.player_repo.update_blinded_until(ctx.target_player_id, blinded_until)

        logger.info(
            "Jugador user_id %d cegado por hechizo %s (duración: %.1fs)",
            ctx.target_player_id,
            ctx.spell_name,
            BLINDNESS_DURATION_SECONDS,
        )

        target_sender = await ctx.get_target_message_sender()
        if target_sender:
            msg = "Te has cegado." if ctx.is_self_cast else "Has sido cegado."
            await target_sender.send_console_msg(msg)

        return SpellEffectResult(success=True)


class DumbEffect(SpellEffect):
    """Efecto de estupidez (no poder lanzar hechizos)."""

    def can_apply(self, ctx: SpellContext) -> bool:
        """Verifica si el hechizo aturde."""
        return ctx.spell_data.get("dumbs", False)

    async def apply_to_npc(self, ctx: SpellContext) -> SpellEffectResult:
        """NPCs no pueden ser aturdidos de esta forma."""
        return SpellEffectResult(success=False)

    async def apply_to_player(self, ctx: SpellContext) -> SpellEffectResult:
        """Aplica estupidez a un jugador."""
        if not ctx.target_player_id or not ctx.player_repo:
            return SpellEffectResult(success=False)

        dumb_until = time.time() + DUMBNESS_DURATION_SECONDS
        await ctx.player_repo.update_dumb_until(ctx.target_player_id, dumb_until)

        logger.info(
            "Jugador user_id %d aturdido por hechizo %s (duración: %.1fs)",
            ctx.target_player_id,
            ctx.spell_name,
            DUMBNESS_DURATION_SECONDS,
        )

        target_sender = await ctx.get_target_message_sender()
        if target_sender:
            msg = "Te has aturdido." if ctx.is_self_cast else "Has sido aturdido."
            await target_sender.send_console_msg(msg)

        return SpellEffectResult(success=True)


class RemoveDumbEffect(SpellEffect):
    """Efecto de remover estupidez."""

    def can_apply(self, ctx: SpellContext) -> bool:
        """Verifica si el hechizo remueve estupidez."""
        return ctx.spell_data.get("removes_stupidity", False)

    async def apply_to_npc(self, ctx: SpellContext) -> SpellEffectResult:
        """NPCs no tienen estupidez."""
        return SpellEffectResult(success=False)

    async def apply_to_player(self, ctx: SpellContext) -> SpellEffectResult:
        """Remueve estupidez de un jugador."""
        if not ctx.target_player_id or not ctx.player_repo:
            return SpellEffectResult(success=False)

        await ctx.player_repo.update_dumb_until(ctx.target_player_id, 0.0)
        logger.info(
            "Estupidez removida de user_id %d por hechizo %s",
            ctx.target_player_id,
            ctx.spell_name,
        )

        target_sender = await ctx.get_target_message_sender()
        if target_sender:
            msg = (
                "Te has quitado el aturdimiento."
                if ctx.is_self_cast
                else "Te han quitado el aturdimiento."
            )
            await target_sender.send_console_msg(msg)

        return SpellEffectResult(success=True)
