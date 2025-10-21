"""Servicio de lógica de negocio para hechizos."""

from __future__ import annotations

import logging
import random
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.map_manager import MapManager
    from src.message_sender import MessageSender
    from src.multiplayer_broadcast_service import MultiplayerBroadcastService
    from src.npc_repository import NPCRepository
    from src.player_repository import PlayerRepository
    from src.spell_catalog import SpellCatalog

logger = logging.getLogger(__name__)


class SpellService:
    """Servicio para gestionar la lógica de hechizos."""

    def __init__(
        self,
        spell_catalog: SpellCatalog,
        player_repo: PlayerRepository,
        npc_repo: NPCRepository,
        map_manager: MapManager,
        broadcast_service: MultiplayerBroadcastService | None = None,
    ) -> None:
        """Inicializa el servicio de hechizos.

        Args:
            spell_catalog: Catálogo de hechizos.
            player_repo: Repositorio de jugadores.
            npc_repo: Repositorio de NPCs.
            map_manager: Gestor de mapas.
            broadcast_service: Servicio de broadcast (opcional).
        """
        self.spell_catalog = spell_catalog
        self.player_repo = player_repo
        self.npc_repo = npc_repo
        self.map_manager = map_manager
        self.broadcast_service = broadcast_service

    async def cast_spell(  # noqa: PLR0914
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
        if stats["min_mana"] < mana_cost:
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
        base_damage = random.randint(min_damage, max_damage)  # noqa: S311

        # Bonus por inteligencia (10% por cada 10 puntos)
        intelligence_bonus = int(base_damage * (stats.get("attr_int", 0) / 100))
        total_damage = base_damage + intelligence_bonus

        # Aplicar daño al NPC
        target_npc.hp = max(0, target_npc.hp - total_damage)
        npc_died = target_npc.hp <= 0

        # Actualizar HP en Redis (si no murió)
        if not npc_died:
            await self.npc_repo.update_npc_hp(target_npc.instance_id, target_npc.hp)

        # Enviar mensajes
        spell_name = spell_data.get("name", "hechizo")
        caster_msg = spell_data.get("caster_msg", "Has lanzado ")
        await message_sender.send_console_msg(
            f"{caster_msg}{target_npc.name}. Daño: {total_damage}"
        )

        # Enviar efecto visual (broadcast a todos en el mapa)
        fx_grh = spell_data.get("fx_grh", 0)
        loops = spell_data.get("loops", 1)
        if fx_grh > 0:
            if self.broadcast_service:
                # Broadcast a todos los jugadores en el mapa
                await self.broadcast_service.broadcast_create_fx(
                    map_id=map_id,
                    x=target_x,
                    y=target_y,
                    fx_id=fx_grh,
                    loops=loops,
                )
            else:
                # Fallback: solo al caster
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

        # Si el NPC murió, eliminarlo del juego
        if npc_died:
            await message_sender.send_console_msg(f"Has matado a {target_npc.name}!")

            # Remover NPC del MapManager
            self.map_manager.remove_npc(map_id, target_npc.char_index)

            # Broadcast CHARACTER_REMOVE a todos los jugadores en el mapa
            if self.broadcast_service:
                await self.broadcast_service.broadcast_character_remove(
                    map_id=map_id,
                    char_index=target_npc.char_index,
                )

            # Eliminar de Redis
            await self.npc_repo.delete_npc(target_npc.instance_id)

            logger.info(
                "NPC %s (CharIndex: %d) eliminado tras ser matado por hechizo de user_id %d",
                target_npc.name,
                target_npc.char_index,
                user_id,
            )

            # TODO: Drop de oro/items, experiencia, respawn

        return True
