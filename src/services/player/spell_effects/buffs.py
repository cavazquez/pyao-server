"""Efectos de buffs/debuffs de hechizos."""

from __future__ import annotations

import logging
import random
import time

from src.services.player.spell_effects.base import SpellContext, SpellEffect, SpellEffectResult

logger = logging.getLogger(__name__)

# Duraciones de buffs/debuffs (segundos)
INVISIBILITY_DURATION_SECONDS = 60.0
MORPH_DURATION_SECONDS = 300.0
STRENGTH_BUFF_DURATION_SECONDS = 1200.0
AGILITY_BUFF_DURATION_SECONDS = 1200.0
STRENGTH_DEBUFF_DURATION_SECONDS = 700.0
AGILITY_DEBUFF_DURATION_SECONDS = 700.0

# Rango de modificadores de atributos
MIN_ATTRIBUTE_MODIFIER = 2
MAX_ATTRIBUTE_MODIFIER = 5

# ID del hechizo Mimetismo
SPELL_ID_MIMICRY = 42


class InvisibilityEffect(SpellEffect):
    """Efecto de invisibilidad."""

    def can_apply(self, ctx: SpellContext) -> bool:
        """Verifica si el hechizo hace invisible."""
        return ctx.spell_data.get("makes_invisible", False)

    async def apply_to_npc(self, ctx: SpellContext) -> SpellEffectResult:
        """NPCs no pueden hacerse invisibles."""
        return SpellEffectResult(success=False)

    async def apply_to_player(self, ctx: SpellContext) -> SpellEffectResult:
        """Aplica invisibilidad a un jugador."""
        if not ctx.target_player_id or not ctx.player_repo or not ctx.map_manager:
            return SpellEffectResult(success=False)

        invisible_until = time.time() + INVISIBILITY_DURATION_SECONDS
        await ctx.player_repo.update_invisible_until(ctx.target_player_id, invisible_until)

        logger.info(
            "Jugador user_id %d invisible por hechizo %s (duración: %.1fs)",
            ctx.target_player_id,
            ctx.spell_name,
            INVISIBILITY_DURATION_SECONDS,
        )

        # Enviar CHARACTER_REMOVE a otros jugadores
        target_position = await ctx.player_repo.get_position(ctx.target_player_id)
        if target_position:
            map_id = target_position["map"]
            other_senders = ctx.map_manager.get_all_message_senders_in_map(
                map_id, exclude_user_id=ctx.target_player_id
            )
            for sender in other_senders:
                await sender.send_character_remove(ctx.target_player_id)
            logger.info(
                "user_id %d invisible - CHARACTER_REMOVE a %d jugadores",
                ctx.target_player_id,
                len(other_senders),
            )

        target_sender = await ctx.get_target_message_sender()
        if target_sender:
            await target_sender.send_console_msg("Te has vuelto invisible.")

        return SpellEffectResult(success=True)


class RemoveInvisibilityEffect(SpellEffect):
    """Efecto de remover invisibilidad."""

    def can_apply(self, ctx: SpellContext) -> bool:
        """Verifica si el hechizo remueve invisibilidad."""
        return ctx.spell_data.get("removes_invisibility", False)

    async def apply_to_npc(self, ctx: SpellContext) -> SpellEffectResult:
        """NPCs no tienen invisibilidad."""
        return SpellEffectResult(success=False)

    async def apply_to_player(self, ctx: SpellContext) -> SpellEffectResult:
        """Remueve invisibilidad de un jugador."""
        if not ctx.target_player_id or not ctx.player_repo:
            return SpellEffectResult(success=False)

        # Verificar si el jugador está invisible
        old_invisible_until = await ctx.player_repo.get_invisible_until(ctx.target_player_id)
        if old_invisible_until <= time.time():
            return SpellEffectResult(success=False)  # No estaba invisible

        await ctx.player_repo.update_invisible_until(ctx.target_player_id, 0.0)
        logger.info(
            "Invisibilidad removida de user_id %d por hechizo %s",
            ctx.target_player_id,
            ctx.spell_name,
        )

        # Enviar CHARACTER_CREATE a otros jugadores
        if ctx.map_manager and ctx.account_repo and ctx.broadcast_service:
            target_position = await ctx.player_repo.get_position(ctx.target_player_id)
            if target_position:
                map_id = target_position["map"]
                account_data = await ctx.account_repo.get_account_by_user_id(ctx.target_player_id)
                if account_data:
                    char_body = int(account_data.get("char_race", 1))
                    char_head = int(account_data.get("char_head", 1))
                    username = account_data.get("username", f"Player{ctx.target_player_id}")
                    if char_body == 0:
                        char_body = 1

                    other_senders = ctx.map_manager.get_all_message_senders_in_map(
                        map_id, exclude_user_id=ctx.target_player_id
                    )
                    for sender in other_senders:
                        await sender.send_character_create(
                            char_index=ctx.target_player_id,
                            body=char_body,
                            head=char_head,
                            heading=target_position.get("heading", 3),
                            x=target_position["x"],
                            y=target_position["y"],
                            name=username,
                        )
                    logger.info(
                        "user_id %d vuelto visible - CHARACTER_CREATE a %d jugadores",
                        ctx.target_player_id,
                        len(other_senders),
                    )

        target_sender = await ctx.get_target_message_sender()
        if target_sender:
            await target_sender.send_console_msg("Ya no eres invisible.")

        return SpellEffectResult(success=True)


class MorphEffect(SpellEffect):
    """Efecto de mimetismo (cambiar apariencia)."""

    def can_apply(self, ctx: SpellContext) -> bool:
        """Verifica si el hechizo morfea."""
        return ctx.spell_data.get("morphs", False) or ctx.spell_id == SPELL_ID_MIMICRY

    async def apply_to_npc(self, ctx: SpellContext) -> SpellEffectResult:
        """El mimetismo no funciona sobre NPCs."""
        if ctx.message_sender:
            await ctx.message_sender.send_console_msg(
                "El mimetismo solo funciona sobre otros jugadores."
            )
        return SpellEffectResult(success=False)

    async def apply_to_player(self, ctx: SpellContext) -> SpellEffectResult:
        """Aplica mimetismo (copia apariencia del target)."""
        if not ctx.target_player_id or not ctx.player_repo or not ctx.account_repo:
            return SpellEffectResult(success=False)

        # Obtener apariencia del target
        target_account_data = await ctx.account_repo.get_account_by_user_id(ctx.target_player_id)
        if not target_account_data:
            if ctx.message_sender:
                await ctx.message_sender.send_console_msg(
                    "No se pudo obtener la apariencia del objetivo."
                )
            return SpellEffectResult(success=False)

        target_body = int(target_account_data.get("char_race", 1))
        target_head = int(target_account_data.get("char_head", 1))
        if target_body == 0:
            target_body = 1

        # Establecer apariencia morfeada
        morphed_until = time.time() + MORPH_DURATION_SECONDS
        await ctx.player_repo.set_morphed_appearance(
            ctx.user_id, target_body, target_head, morphed_until
        )

        # Obtener posición del caster
        caster_position = await ctx.player_repo.get_position(ctx.user_id)
        if not caster_position:
            if ctx.message_sender:
                await ctx.message_sender.send_console_msg("No se pudo obtener tu posición.")
            return SpellEffectResult(success=False)

        map_id = caster_position["map"]
        caster_heading = caster_position.get("heading", 3)

        # Enviar CHARACTER_CHANGE al caster
        if ctx.message_sender:
            await ctx.message_sender.send_character_change(
                char_index=ctx.user_id,
                body=target_body,
                head=target_head,
                heading=caster_heading,
            )

        # Broadcast CHARACTER_CHANGE a otros jugadores
        if ctx.map_manager:
            other_senders = ctx.map_manager.get_all_message_senders_in_map(
                map_id, exclude_user_id=ctx.user_id
            )
            for sender in other_senders:
                await sender.send_character_change(
                    char_index=ctx.user_id,
                    body=target_body,
                    head=target_head,
                    heading=caster_heading,
                )
            logger.debug(
                "Mimetismo de user_id %d notificado a %d jugadores en mapa %d",
                ctx.user_id,
                len(other_senders),
                map_id,
            )

        logger.info(
            "user_id %d morfeado a apariencia de user_id %d (body=%d head=%d) hasta %.2f",
            ctx.user_id,
            ctx.target_player_id,
            target_body,
            target_head,
            morphed_until,
        )

        return SpellEffectResult(success=True)


class StrengthBuffEffect(SpellEffect):
    """Efecto de aumentar fuerza."""

    def can_apply(self, ctx: SpellContext) -> bool:
        """Verifica si el hechizo aumenta fuerza."""
        return ctx.spell_data.get("increases_strength", False)

    async def apply_to_npc(self, ctx: SpellContext) -> SpellEffectResult:
        """NPCs no reciben buffs de fuerza."""
        return SpellEffectResult(success=False)

    async def apply_to_player(self, ctx: SpellContext) -> SpellEffectResult:
        """Aplica buff de fuerza a un jugador."""
        return await self._apply_strength_modifier(ctx, is_buff=True)

    async def _apply_strength_modifier(self, ctx: SpellContext, is_buff: bool) -> SpellEffectResult:
        """Aplica modificador de fuerza."""
        if not ctx.target_player_id or not ctx.player_repo:
            return SpellEffectResult(success=False)

        modifier_value = random.randint(MIN_ATTRIBUTE_MODIFIER, MAX_ATTRIBUTE_MODIFIER)
        if not is_buff:
            modifier_value = -modifier_value

        duration = STRENGTH_BUFF_DURATION_SECONDS if is_buff else STRENGTH_DEBUFF_DURATION_SECONDS
        expires_at = time.time() + duration

        await ctx.player_repo.set_strength_modifier(
            ctx.target_player_id, expires_at, modifier_value
        )

        logger.info(
            "user_id %d recibió %s fuerza (%+d) hasta %.2f (%.1fs) - %s",
            ctx.target_player_id,
            "buff" if is_buff else "debuff",
            modifier_value,
            expires_at,
            duration,
            ctx.spell_name,
        )

        # Enviar actualización de atributos
        attributes = await ctx.player_repo.get_player_attributes(ctx.target_player_id)
        if attributes:
            target_sender = await ctx.get_target_message_sender()
            if target_sender:
                await target_sender.send_update_strength_and_dexterity(
                    strength=attributes.strength,
                    dexterity=attributes.agility,
                )

        return SpellEffectResult(success=True, data={"modifier": modifier_value})


class StrengthDebuffEffect(StrengthBuffEffect):
    """Efecto de reducir fuerza."""

    def can_apply(self, ctx: SpellContext) -> bool:
        """Verifica si el hechizo reduce fuerza."""
        return ctx.spell_data.get("decreases_strength", False)

    async def apply_to_player(self, ctx: SpellContext) -> SpellEffectResult:
        """Aplica debuff de fuerza a un jugador."""
        return await self._apply_strength_modifier(ctx, is_buff=False)


class AgilityBuffEffect(SpellEffect):
    """Efecto de aumentar agilidad."""

    def can_apply(self, ctx: SpellContext) -> bool:
        """Verifica si el hechizo aumenta agilidad."""
        return ctx.spell_data.get("increases_agility", False)

    async def apply_to_npc(self, ctx: SpellContext) -> SpellEffectResult:
        """NPCs no reciben buffs de agilidad."""
        return SpellEffectResult(success=False)

    async def apply_to_player(self, ctx: SpellContext) -> SpellEffectResult:
        """Aplica buff de agilidad a un jugador."""
        return await self._apply_agility_modifier(ctx, is_buff=True)

    async def _apply_agility_modifier(self, ctx: SpellContext, is_buff: bool) -> SpellEffectResult:
        """Aplica modificador de agilidad."""
        if not ctx.target_player_id or not ctx.player_repo:
            return SpellEffectResult(success=False)

        modifier_value = random.randint(MIN_ATTRIBUTE_MODIFIER, MAX_ATTRIBUTE_MODIFIER)
        if not is_buff:
            modifier_value = -modifier_value

        duration = AGILITY_BUFF_DURATION_SECONDS if is_buff else AGILITY_DEBUFF_DURATION_SECONDS
        expires_at = time.time() + duration

        await ctx.player_repo.set_agility_modifier(ctx.target_player_id, expires_at, modifier_value)

        logger.info(
            "user_id %d recibió %s agilidad (%+d) hasta %.2f (%.1fs) - %s",
            ctx.target_player_id,
            "buff" if is_buff else "debuff",
            modifier_value,
            expires_at,
            duration,
            ctx.spell_name,
        )

        # Enviar actualización de atributos
        attributes = await ctx.player_repo.get_player_attributes(ctx.target_player_id)
        if attributes:
            target_sender = await ctx.get_target_message_sender()
            if target_sender:
                await target_sender.send_update_strength_and_dexterity(
                    strength=attributes.strength,
                    dexterity=attributes.agility,
                )

        return SpellEffectResult(success=True, data={"modifier": modifier_value})


class AgilityDebuffEffect(AgilityBuffEffect):
    """Efecto de reducir agilidad."""

    def can_apply(self, ctx: SpellContext) -> bool:
        """Verifica si el hechizo reduce agilidad."""
        return ctx.spell_data.get("decreases_agility", False)

    async def apply_to_player(self, ctx: SpellContext) -> SpellEffectResult:
        """Aplica debuff de agilidad a un jugador."""
        return await self._apply_agility_modifier(ctx, is_buff=False)
