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

        # Obtener stats del jugador
        stats = await self.player_repo.get_stats(user_id)
        if not stats:
            logger.warning("No se pudieron obtener stats del jugador %d", user_id)
            return False

        # Verificar mana suficiente
        mana_cost = spell_data.get("mana_cost", 0)
        current_mana = stats.get("min_mana", 0)
        if current_mana < mana_cost:
            spell_name = spell_data.get("name", f"hechizo {spell_id}")
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

        # Buscar target en la posición
        target_npc = None
        all_npcs = self.map_manager.get_npcs_in_map(map_id)
        for npc in all_npcs:
            if npc.x == target_x and npc.y == target_y:
                target_npc = npc
                break

        if not target_npc:
            await message_sender.send_console_msg("No hay objetivo válido en esa posición.")
            return False

        # Reducir mana
        stats["min_mana"] -= mana_cost
        await self.player_repo.set_stats(user_id=user_id, **stats)
        await message_sender.send_update_user_stats(**stats)

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

        # Obtener nombre del hechizo para usar en mensajes y estados
        spell_name = spell_data.get("name", "hechizo")

        # Aplicar efectos de estado si el hechizo es tipo 2 (Estados)
        spell_type = spell_data.get("type", SPELL_TYPE_DAMAGE)
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

        # Enviar mensajes
        caster_msg = spell_data.get("caster_msg", "Has lanzado ")
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

        return True
