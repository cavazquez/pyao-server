"""Servicio de lógica de negocio para hechizos."""

from __future__ import annotations

import logging
import random
import time
from typing import TYPE_CHECKING, Any

from src.services.player.spell_effects import SpellContext, get_spell_effect_registry

if TYPE_CHECKING:
    from src.game.map_manager import MapManager
    from src.messaging.message_sender import MessageSender
    from src.models.spell_catalog import SpellCatalog
    from src.repositories.account_repository import AccountRepository
    from src.repositories.npc_repository import NPCRepository
    from src.repositories.player_repository import PlayerRepository
    from src.services.multiplayer_broadcast_service import MultiplayerBroadcastService
    from src.services.npc.npc_death_service import NPCDeathService
    from src.services.npc.npc_service import NPCService
    from src.services.npc.summon_service import SummonService

logger = logging.getLogger(__name__)


class SpellService:
    """Servicio para gestionar la lógica de hechizos usando Strategy Pattern."""

    def __init__(
        self,
        spell_catalog: SpellCatalog,
        player_repo: PlayerRepository,
        npc_repo: NPCRepository,
        map_manager: MapManager,
        npc_death_service: NPCDeathService | None = None,
        account_repo: AccountRepository | None = None,
        broadcast_service: MultiplayerBroadcastService | None = None,
        npc_service: NPCService | None = None,
        summon_service: SummonService | None = None,
    ) -> None:
        """Inicializa el servicio de hechizos.

        Args:
            spell_catalog: Catálogo de hechizos.
            player_repo: Repositorio de jugadores.
            npc_repo: Repositorio de NPCs.
            map_manager: Gestor de mapas.
            npc_death_service: Servicio de muerte de NPCs (opcional).
            account_repo: Repositorio de cuentas (opcional).
            broadcast_service: Servicio de broadcast (opcional).
            npc_service: Servicio de NPCs (opcional).
            summon_service: Servicio de invocación (opcional).
        """
        self.spell_catalog = spell_catalog
        self.player_repo = player_repo
        self.npc_repo = npc_repo
        self.map_manager = map_manager
        self.npc_death_service = npc_death_service
        self.account_repo = account_repo
        self.broadcast_service = broadcast_service
        self.npc_service = npc_service
        self.summon_service = summon_service
        self._effect_registry = get_spell_effect_registry()

    async def cast_spell(
        self,
        user_id: int,
        spell_id: int,
        target_x: int,
        target_y: int,
        message_sender: MessageSender,
    ) -> bool:
        """Lanza un hechizo usando el sistema de efectos.

        Args:
            user_id: ID del jugador que lanza el hechizo.
            spell_id: ID del hechizo a lanzar.
            target_x: Coordenada X del objetivo.
            target_y: Coordenada Y del objetivo.
            message_sender: Enviador de mensajes.

        Returns:
            True si el hechizo se lanzó exitosamente, False en caso contrario.
        """
        # Validar y obtener datos del hechizo
        spell_data = self.spell_catalog.get_spell_data(spell_id)
        if not spell_data:
            logger.warning("Hechizo %d no existe", spell_id)
            return False

        spell_name = spell_data.get("name", "hechizo")

        # Verificar si el jugador está aturdido
        if not await self._can_cast(user_id, message_sender):
            return False

        # Verificar mana
        mana_cost = spell_data.get("mana_cost", 0)
        if not await self._has_enough_mana(user_id, mana_cost, spell_name, message_sender):
            return False

        # Obtener posición del jugador
        position = await self.player_repo.get_position(user_id)
        if not position:
            return False

        # Buscar target
        target_npc, target_player_id = await self._find_target(
            position["map"], target_x, target_y, user_id, spell_data, message_sender
        )
        if target_npc is None and target_player_id is None:
            return False

        # Reducir mana
        min_mana, max_mana = await self.player_repo.get_mana(user_id)
        new_min_mana = max(0, min_mana - mana_cost)
        await self.player_repo.update_mana(user_id, new_min_mana)

        # Obtener stats completos para enviar actualización
        stats = await self.player_repo.get_player_stats(user_id)
        if stats:
            await message_sender.send_update_user_stats(
                max_hp=stats.max_hp,
                min_hp=stats.min_hp,
                max_mana=stats.max_mana,
                min_mana=new_min_mana,
                max_sta=stats.max_sta,
                min_sta=stats.min_sta,
                gold=stats.gold,
                level=stats.level,
                elu=stats.elu,
                experience=stats.experience,
            )

        # Obtener stats del target si es un jugador (para compatibilidad con SpellContext)
        target_player_stats = None
        if target_player_id:
            target_stats = await self.player_repo.get_player_stats(target_player_id)
            if not target_stats and target_player_id != user_id:
                await message_sender.send_console_msg("Objetivo inválido.")
                return False
            # Mantener como dict para compatibilidad con SpellContext (se puede refactorizar después)
            if target_stats:
                target_player_stats = target_stats.to_dict()

        # Calcular daño/curación base
        base_amount, total_amount = await self._calculate_amount(spell_data, user_id)

        # Obtener stats del caster para SpellContext (compatibilidad)
        caster_stats = await self.player_repo.get_player_stats(user_id)
        caster_stats_dict = caster_stats.to_dict() if caster_stats else {}

        # Crear contexto para los efectos
        ctx = SpellContext(
            user_id=user_id,
            caster_stats=caster_stats_dict,
            caster_position=position,
            spell_id=spell_id,
            spell_data=spell_data,
            spell_name=spell_name,
            target_x=target_x,
            target_y=target_y,
            target_npc=target_npc,
            target_player_id=target_player_id,
            target_player_stats=target_player_stats,
            base_amount=base_amount,
            total_amount=total_amount,
            message_sender=message_sender,
            player_repo=self.player_repo,
            npc_repo=self.npc_repo,
            account_repo=self.account_repo,
            map_manager=self.map_manager,
            broadcast_service=self.broadcast_service,
            npc_service=self.npc_service,
            npc_death_service=self.npc_death_service,
            summon_service=self.summon_service,
            spell_catalog=self.spell_catalog,
        )

        # Aplicar todos los efectos
        results = await self._effect_registry.apply_effects(ctx)

        # Verificar si algún efecto detuvo el procesamiento
        for result in results:
            if result.stop_processing:
                return result.success

        # Enviar mensajes finales y efectos visuales
        await self._send_final_messages(ctx)
        await self._send_visual_effects(ctx)

        # Manejar muerte de NPC si aplica
        if ctx.npc_died and ctx.target_npc:
            await self._handle_npc_death(ctx)

        return True

    async def _can_cast(self, user_id: int, message_sender: MessageSender) -> bool:
        """Verifica si el jugador puede lanzar hechizos.

        Returns:
            True si puede lanzar, False si está aturdido.
        """
        dumb_until = await self.player_repo.get_dumb_until(user_id)
        current_time = time.time()
        if dumb_until > current_time:
            remaining_time = dumb_until - current_time
            logger.info(
                "user_id %d intentó lanzar hechizo pero está aturdido. Tiempo: %.1f",
                user_id,
                remaining_time,
            )
            await message_sender.send_console_msg(
                f"No puedes lanzar hechizos. Estás aturdido (restantes: {int(remaining_time)}s)."
            )
            return False
        return True

    async def _has_enough_mana(
        self,
        user_id: int,
        mana_cost: int,
        spell_name: str,
        message_sender: MessageSender,
    ) -> bool:
        """Verifica si el jugador tiene suficiente mana.

        Returns:
            True si tiene mana suficiente, False en caso contrario.
        """
        min_mana, _ = await self.player_repo.get_mana(user_id)
        if min_mana < mana_cost:
            logger.info(
                "user_id %d no tiene mana para %s: %d/%d",
                user_id,
                spell_name,
                min_mana,
                mana_cost,
            )
            await message_sender.send_console_msg("No tienes suficiente mana.")
            return False
        return True

    async def _find_target(
        self,
        map_id: int,
        target_x: int,
        target_y: int,
        user_id: int,
        spell_data: dict[str, Any],
        message_sender: MessageSender,
    ) -> tuple[Any, int | None]:
        """Busca el target del hechizo (NPC o jugador).

        Returns:
            Tupla (target_npc, target_player_id), ambos pueden ser None.
        """
        target_npc = None
        target_player_id = None

        # Buscar NPCs
        for npc in self.map_manager.get_npcs_in_map(map_id):
            if npc.x == target_x and npc.y == target_y:
                target_npc = npc
                break

        # Si no hay NPC, buscar jugadores
        if not target_npc:
            for player_id in self.map_manager.get_players_in_map(map_id):
                player_pos = await self.player_repo.get_position(player_id)
                if (
                    player_pos
                    and player_pos["x"] == target_x
                    and player_pos["y"] == target_y
                    and player_pos["map"] == map_id
                ):
                    target_player_id = player_id
                    break

        # Si no hay target, verificar auto-cast
        if not target_npc and not target_player_id:
            spell_target = spell_data.get("target", 3)
            if spell_target in {1, 3}:  # Usuario o Usuario Y NPC
                target_player_id = user_id
            else:
                await message_sender.send_console_msg("No hay objetivo válido en esa posición.")
                return None, None

        return target_npc, target_player_id

    async def _calculate_amount(
        self, spell_data: dict[str, Any], user_id: int
    ) -> tuple[int, int]:
        """Calcula el daño o curación del hechizo.

        Returns:
            Tupla (base_amount, total_amount) con bonus de inteligencia.
        """
        min_damage = spell_data.get("min_damage", 0)
        max_damage = spell_data.get("max_damage", 0)
        base_amount = random.randint(min_damage, max_damage) if max_damage > 0 else 0

        # Bonus por inteligencia
        attributes = await self.player_repo.get_player_attributes(user_id)
        intelligence = attributes.intelligence if attributes else 10
        intelligence_bonus = int(base_amount * (intelligence / 100))
        total_amount = base_amount + intelligence_bonus

        return base_amount, total_amount

    async def _send_final_messages(self, ctx: SpellContext) -> None:
        """Envía mensajes finales del hechizo."""
        if not ctx.message_sender:
            return

        caster_msg = ctx.spell_data.get("caster_msg", "Has lanzado ")

        if ctx.target_npc:
            if ctx.spell_data.get("heals_hp", False):
                await ctx.message_sender.send_console_msg(f"{caster_msg}{ctx.target_npc.name}.")
            else:
                await ctx.message_sender.send_console_msg(
                    f"{caster_msg}{ctx.target_npc.name}. Daño: {ctx.total_amount}"
                )

            logger.info(
                "user_id %d lanzó %s sobre NPC %s",
                ctx.user_id,
                ctx.spell_name,
                ctx.target_npc.name,
            )
        elif ctx.target_player_id:
            if ctx.is_self_cast:
                self_msg = ctx.spell_data.get("self_msg", "Te has lanzado ")
                await ctx.message_sender.send_console_msg(f"{self_msg}{ctx.spell_name}.")
            else:
                await ctx.message_sender.send_console_msg(f"{caster_msg}{ctx.target_name}.")

            logger.info(
                "user_id %d lanzó %s sobre %s",
                ctx.user_id,
                ctx.spell_name,
                ctx.target_name,
            )

    async def _send_visual_effects(self, ctx: SpellContext) -> None:
        """Envía efectos visuales del hechizo."""
        if not ctx.message_sender:
            return

        fx_grh = ctx.spell_data.get("fx_grh", 0)
        loops = ctx.spell_data.get("loops", 1)
        if fx_grh > 0:
            await ctx.message_sender.send_create_fx_at_position(
                ctx.target_x, ctx.target_y, fx_grh, loops
            )

    async def _handle_npc_death(self, ctx: SpellContext) -> None:
        """Maneja la muerte de un NPC por hechizo."""
        if not ctx.target_npc or not ctx.message_sender:
            return

        if self.npc_death_service:
            experience = ctx.target_npc.level * 10
            await self.npc_death_service.handle_npc_death(
                npc=ctx.target_npc,
                killer_user_id=ctx.user_id,
                experience=experience,
                message_sender=ctx.message_sender,
                death_reason="hechizo",
            )
        else:
            # Fallback si no hay death service
            await ctx.message_sender.send_console_msg(f"Has matado a {ctx.target_npc.name}!")
            logger.warning("NPCDeathService no disponible - NPC no fue eliminado correctamente")
