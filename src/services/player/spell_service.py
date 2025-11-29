"""Servicio de lógica de negocio para hechizos."""

from __future__ import annotations

import logging
import random
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.game.map_manager import MapManager
    from src.messaging.message_sender import MessageSender
    from src.models.spell_catalog import SpellCatalog
    from src.repositories.npc_repository import NPCRepository
    from src.repositories.player_repository import PlayerRepository
    from src.services.npc.npc_death_service import NPCDeathService

logger = logging.getLogger(__name__)

# Constantes para tipos de hechizos
SPELL_TYPE_DAMAGE = 1  # Tipo 1: Daño
SPELL_TYPE_STATUS = 2  # Tipo 2: Estados

# ID del hechizo Paralizar
SPELL_ID_PARALYZE = 9

# Duración de envenenamiento por defecto (segundos)
POISON_DURATION_SECONDS = 30.0

# Duración de inmovilización por defecto (segundos)
IMMOBILIZATION_DURATION_SECONDS = 30.0

# Duración de ceguera por defecto (segundos)
# En VB6 es IntervaloParalizado / 3 (aproximadamente 3-4 segundos)
BLINDNESS_DURATION_SECONDS = 10.0


class SpellService:
    """Servicio para gestionar la lógica de hechizos."""

    def __init__(
        self,
        spell_catalog: SpellCatalog,
        player_repo: PlayerRepository,
        npc_repo: NPCRepository,
        map_manager: MapManager,
        npc_death_service: NPCDeathService | None = None,
    ) -> None:
        """Inicializa el servicio de hechizos.

        Args:
            spell_catalog: Catálogo de hechizos.
            player_repo: Repositorio de jugadores.
            npc_repo: Repositorio de NPCs.
            map_manager: Gestor de mapas.
            npc_death_service: Servicio de muerte de NPCs (opcional).
        """
        self.spell_catalog = spell_catalog
        self.player_repo = player_repo
        self.npc_repo = npc_repo
        self.map_manager = map_manager
        self.npc_death_service = npc_death_service

    async def cast_spell(  # noqa: PLR0914, PLR0915
        self,
        user_id: int,
        spell_id: int,
        target_x: int,
        target_y: int,
        message_sender: MessageSender,
    ) -> bool:
        """Lanza un hechizo.

        Args:
            user_id: ID del jugador que lanza el hechizo.
            spell_id: ID del hechizo a lanzar.
            target_x: Coordenada X del objetivo.
            target_y: Coordenada Y del objetivo.
            message_sender: Enviador de mensajes.

        Returns:
            True si el hechizo se lanzó exitosamente, False en caso contrario.
        """
        # Obtener datos del hechizo
        spell_data = self.spell_catalog.get_spell_data(spell_id)
        if not spell_data:
            logger.warning("Hechizo %d no existe", spell_id)
            return False

        # Obtener nombre del hechizo para usar en mensajes
        spell_name = spell_data.get("name", "hechizo")

        # Obtener stats del jugador
        stats = await self.player_repo.get_stats(user_id)
        if not stats:
            logger.warning("No se pudieron obtener stats del jugador %d", user_id)
            return False

        # Verificar mana suficiente
        mana_cost = spell_data.get("mana_cost", 0)
        current_mana = stats.get("min_mana", 0)
        if current_mana < mana_cost:
            logger.info(
                "user_id %d no tiene suficiente mana para lanzar %s: %d/%d requeridos",
                user_id,
                spell_name,
                current_mana,
                mana_cost,
            )
            await message_sender.send_console_msg("No tienes suficiente mana.")
            return False

        # Obtener posición del jugador
        position = await self.player_repo.get_position(user_id)
        if not position:
            return False

        map_id = position["map"]

        # Buscar target en la posición (NPC o jugador)
        target_npc = None
        target_player_id: int | None = None

        # Primero buscar NPCs
        all_npcs = self.map_manager.get_npcs_in_map(map_id)
        for npc in all_npcs:
            if npc.x == target_x and npc.y == target_y:
                target_npc = npc
                break

        # Si no hay NPC, buscar jugadores en esa posición
        if not target_npc:
            player_ids = self.map_manager.get_players_in_map(map_id)
            for player_id in player_ids:
                player_pos = await self.player_repo.get_position(player_id)
                if (
                    player_pos
                    and player_pos["x"] == target_x
                    and player_pos["y"] == target_y
                    and player_pos["map"] == map_id
                ):
                    target_player_id = player_id
                    break

        # Si no hay target válido, verificar si es auto-cast permitido
        if not target_npc and not target_player_id:
            spell_target = spell_data.get("target", 3)  # Default: Usuario Y NPC
            # Auto-cast permitido si: target = 1 (Usuario) o target = 3 (Usuario Y NPC)
            if spell_target in {1, 3}:  # Target = Usuario o Usuario Y NPC
                target_player_id = user_id
                logger.debug(
                    "Auto-cast activado para hechizo %s (target=%d) sobre user_id %d",
                    spell_name,
                    spell_target,
                    user_id,
                )
            else:
                await message_sender.send_console_msg("No hay objetivo válido en esa posición.")
                return False

        # Reducir mana
        stats["min_mana"] -= mana_cost
        await self.player_repo.set_stats(user_id=user_id, **stats)
        await message_sender.send_update_user_stats(**stats)

        # Obtener tipo del hechizo para usar en efectos
        spell_type = spell_data.get("type", SPELL_TYPE_DAMAGE)

        # Procesar según el tipo de target
        npc_died = False
        target_name = "objetivo"

        if target_npc:
            # Target es un NPC
            target_name = target_npc.name

            # Calcular daño
            min_damage = spell_data.get("min_damage", 0)
            max_damage = spell_data.get("max_damage", 0)
            base_damage = random.randint(min_damage, max_damage)

            # Bonus por inteligencia (10% por cada 10 puntos)
            intelligence_bonus = int(base_damage * (stats.get("attr_int", 0) / 100))
            total_damage = base_damage + intelligence_bonus

            # Aplicar daño al NPC
            target_npc.hp = max(0, target_npc.hp - total_damage)
            npc_died = target_npc.hp <= 0

            # Actualizar HP en Redis (si no murió)
            if not npc_died:
                await self.npc_repo.update_npc_hp(target_npc.instance_id, target_npc.hp)

            # Aplicar efectos de estado si el hechizo es tipo 2 (Estados)
            if spell_type == SPELL_TYPE_STATUS and not npc_died:
                spell_name_lower = spell_name.lower()
                if "paralizar" in spell_name_lower or spell_id == SPELL_ID_PARALYZE:
                    # Aplicar parálisis (duración: 10 segundos por defecto)
                    paralysis_duration = 10.0  # Segundos
                    paralyzed_until = time.time() + paralysis_duration
                    target_npc.paralyzed_until = paralyzed_until
                    await self.npc_repo.update_npc_paralyzed_until(
                        target_npc.instance_id, paralyzed_until
                    )
                    logger.info(
                        "NPC %s paralizado hasta %.2f (duración: %.1fs)",
                        target_npc.name,
                        paralyzed_until,
                        paralysis_duration,
                    )

            # Aplicar envenenamiento si el hechizo envenena (independiente del tipo)
            if spell_data.get("poisons", False) and not npc_died:
                poisoned_until = time.time() + POISON_DURATION_SECONDS
                target_npc.poisoned_until = poisoned_until
                target_npc.poisoned_by_user_id = user_id  # Rastrear quién envenenó
                await self.npc_repo.update_npc_poisoned_until(
                    target_npc.instance_id, poisoned_until, poisoned_by_user_id=user_id
                )
                logger.info(
                    "NPC %s envenenado hasta %.2f (duración: %.1fs) por user_id %d con hechizo %s",
                    target_npc.name,
                    poisoned_until,
                    POISON_DURATION_SECONDS,
                    user_id,
                    spell_name,
                )

        elif target_player_id:
            # Target es un jugador
            target_player_stats = await self.player_repo.get_stats(target_player_id)
            if not target_player_stats:
                await message_sender.send_console_msg("Objetivo inválido.")
                return False

            target_player_name = (
                self.map_manager.get_player_username(target_player_id)
                or f"Jugador {target_player_id}"
            )

            # Verificar si es auto-cast
            target_name = "tí mismo" if target_player_id == user_id else target_player_name

            # Calcular daño (si el hechizo hace daño)
            min_damage = spell_data.get("min_damage", 0)
            max_damage = spell_data.get("max_damage", 0)
            if min_damage > 0 or max_damage > 0:
                base_damage = random.randint(min_damage, max_damage)
                intelligence_bonus = int(base_damage * (stats.get("attr_int", 0) / 100))
                total_damage = base_damage + intelligence_bonus

                # Aplicar daño al jugador
                current_hp = target_player_stats.get("min_hp", 0)
                new_hp = max(0, current_hp - total_damage)
                target_player_stats["min_hp"] = new_hp
                await self.player_repo.set_stats(user_id=target_player_id, **target_player_stats)

                # Notificar al jugador objetivo (si no es auto-cast)
                if target_player_id != user_id:
                    target_message_sender = self.map_manager.get_player_message_sender(
                        target_player_id
                    )
                    if target_message_sender:
                        await target_message_sender.send_update_user_stats(**target_player_stats)
                        await target_message_sender.send_console_msg(
                            f"{spell_name} te ha causado {total_damage} de daño."
                        )

                # Si el jugador murió
                if new_hp <= 0:
                    logger.info(
                        "Jugador user_id %d murió por hechizo %s (daño: %d)",
                        target_player_id,
                        spell_name,
                        total_damage,
                    )
            else:
                total_damage = 0

            # Aplicar envenenamiento si el hechizo envenena
            if spell_data.get("poisons", False):
                poisoned_until = time.time() + POISON_DURATION_SECONDS
                await self.player_repo.update_poisoned_until(target_player_id, poisoned_until)
                logger.info(
                    "Jugador user_id %d envenenado hasta %.2f (duración: %.1fs) por hechizo %s",
                    target_player_id,
                    poisoned_until,
                    POISON_DURATION_SECONDS,
                    spell_name,
                )
                if target_player_id == user_id:
                    await message_sender.send_console_msg("Te has envenenado.")
                else:
                    target_message_sender = self.map_manager.get_player_message_sender(
                        target_player_id
                    )
                    if target_message_sender:
                        await target_message_sender.send_console_msg("Has sido envenenado.")

            # Aplicar inmovilización si el hechizo inmoviliza
            if spell_data.get("immobilizes", False):
                immobilized_until = time.time() + IMMOBILIZATION_DURATION_SECONDS
                await self.player_repo.update_immobilized_until(target_player_id, immobilized_until)
                logger.info(
                    "Jugador user_id %d inmovilizado hasta %.2f (duración: %.1fs) por hechizo %s",
                    target_player_id,
                    immobilized_until,
                    IMMOBILIZATION_DURATION_SECONDS,
                    spell_name,
                )
                if target_player_id == user_id:
                    await message_sender.send_console_msg("Te has inmovilizado.")
                else:
                    target_message_sender = self.map_manager.get_player_message_sender(
                        target_player_id
                    )
                    if target_message_sender:
                        await target_message_sender.send_console_msg("Has sido inmovilizado.")

            # Aplicar ceguera si el hechizo ciega
            if spell_data.get("blinds", False):
                blinded_until = time.time() + BLINDNESS_DURATION_SECONDS
                await self.player_repo.update_blinded_until(target_player_id, blinded_until)
                logger.info(
                    "Jugador user_id %d cegado hasta %.2f (duración: %.1fs) por hechizo %s",
                    target_player_id,
                    blinded_until,
                    BLINDNESS_DURATION_SECONDS,
                    spell_name,
                )
                if target_player_id == user_id:
                    await message_sender.send_console_msg("Te has cegado.")
                else:
                    target_message_sender = self.map_manager.get_player_message_sender(
                        target_player_id
                    )
                    if target_message_sender:
                        await target_message_sender.send_console_msg("Has sido cegado.")

        # Enviar mensajes según el tipo de target
        caster_msg = spell_data.get("caster_msg", "Has lanzado ")
        if target_npc:
            total_damage = base_damage + intelligence_bonus
            await message_sender.send_console_msg(
                f"{caster_msg}{target_npc.name}. Daño: {total_damage}"
            )

            # Enviar efecto visual (solo al caster por ahora, broadcast lo maneja el death service)
            fx_grh = spell_data.get("fx_grh", 0)
            loops = spell_data.get("loops", 1)
            if fx_grh > 0:
                await message_sender.send_create_fx_at_position(target_x, target_y, fx_grh, loops)

            # Log
            logger.info(
                "user_id %d lanzó %s sobre NPC %s. Daño: %d (HP restante: %d/%d)",
                user_id,
                spell_name,
                target_npc.name,
                total_damage,
                target_npc.hp,
                target_npc.max_hp,
            )

            # Si el NPC murió, usar servicio centralizado
            if npc_died and self.npc_death_service:
                # Calcular experiencia (similar a CombatService)
                experience = target_npc.level * 10  # 10 EXP por nivel del NPC

                # Delegar toda la lógica de muerte al servicio centralizado
                await self.npc_death_service.handle_npc_death(
                    npc=target_npc,
                    killer_user_id=user_id,
                    experience=experience,
                    message_sender=message_sender,
                    death_reason="hechizo",
                )
            elif npc_died:
                # Fallback si no hay death service
                await message_sender.send_console_msg(f"Has matado a {target_npc.name}!")
                logger.warning("NPCDeathService no disponible - NPC no fue eliminado correctamente")
        elif target_player_id:
            # Mensaje para jugador target
            if target_player_id == user_id:
                self_msg = spell_data.get("self_msg", "Te has lanzado ")
                await message_sender.send_console_msg(f"{self_msg}{spell_name}.")
            else:
                await message_sender.send_console_msg(f"{caster_msg}{target_name}.")

            # Enviar efecto visual
            fx_grh = spell_data.get("fx_grh", 0)
            loops = spell_data.get("loops", 1)
            if fx_grh > 0:
                await message_sender.send_create_fx_at_position(target_x, target_y, fx_grh, loops)

            # Log
            logger.info(
                "user_id %d lanzó %s sobre jugador %s (user_id %d)",
                user_id,
                spell_name,
                target_name,
                target_player_id,
            )

        return True
