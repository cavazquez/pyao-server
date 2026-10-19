"""Servicio para manejar la muerte de NPCs."""

import logging
from typing import TYPE_CHECKING

from src.config.config_manager import ConfigManager
from src.services.npc.rewards.experience import ExperienceComponent

if TYPE_CHECKING:
    from src.game.map_manager import MapManager
    from src.messaging.message_sender import MessageSender
    from src.models.item_catalog import ItemCatalog
    from src.models.npc import NPC
    from src.models.party import Party
    from src.repositories.npc_repository import NPCRepository
    from src.repositories.player_repository import PlayerRepository
    from src.services.multiplayer_broadcast_service import MultiplayerBroadcastService
    from src.services.npc.loot_table_service import LootTableService
    from src.services.npc.npc_respawn_service import NPCRespawnService
    from src.services.npc.random_spawn_service import RandomSpawnService
    from src.services.party_service import PartyService

logger = logging.getLogger(__name__)
config_manager = ConfigManager()


class NPCDeathService:
    """Servicio centralizado para manejar la muerte de NPCs."""

    def __init__(
        self,
        map_manager: MapManager,
        npc_repo: NPCRepository,
        player_repo: PlayerRepository,
        broadcast_service: MultiplayerBroadcastService,
        loot_table_service: LootTableService | None = None,
        item_catalog: ItemCatalog | None = None,
        npc_respawn_service: NPCRespawnService | None = None,
        party_service: PartyService | None = None,
        random_spawn_service: RandomSpawnService | None = None,
    ) -> None:
        """Inicializa el servicio de muerte de NPCs.

        Args:
            map_manager: Gestor de mapas.
            npc_repo: Repositorio de NPCs.
            player_repo: Repositorio de jugadores.
            broadcast_service: Servicio de broadcast.
            loot_table_service: Servicio de loot tables (opcional).
            item_catalog: Catálogo de items (opcional).
            npc_respawn_service: Servicio de respawn (opcional).
            party_service: Servicio de parties (opcional).
            random_spawn_service: Servicio de spawns aleatorios (opcional).
        """
        self.map_manager = map_manager
        self.npc_repo = npc_repo
        self.player_repo = player_repo
        self.broadcast_service = broadcast_service
        self.loot_table_service = loot_table_service
        self.item_catalog = item_catalog
        self.npc_respawn_service = npc_respawn_service
        self.party_service = party_service
        self.random_spawn_service = random_spawn_service
        self._experience = ExperienceComponent(self)

    async def handle_npc_death(
        self,
        npc: NPC,
        killer_user_id: int,
        experience: int,
        message_sender: MessageSender,
        death_reason: str = "combate",
    ) -> None:
        """Maneja completamente la muerte de un NPC.

        Args:
            npc: NPC que murió.
            killer_user_id: ID del jugador que mató al NPC.
            experience: Experiencia a otorgar.
            message_sender: MessageSender del jugador.
            death_reason: Razón de la muerte ("combate", "hechizo", etc).
        """
        # Mensaje de muerte (solo si no está en party,
        # el mensaje de party se envía en _give_experience)
        if not self.party_service or not await self.party_service.get_party_info(killer_user_id):
            await message_sender.send_console_msg(
                f"¡Has matado a {npc.name}! Ganaste {experience} EXP."
            )

        # Dar experiencia al jugador o distribuir a party
        await self._give_experience(killer_user_id, experience, message_sender, npc)

        # Reproducir sonido de muerte del NPC (Snd3) si está disponible
        if npc.snd3 > 0:
            await self.broadcast_service.broadcast_play_wave(
                map_id=npc.map_id, wave_id=npc.snd3, x=npc.x, y=npc.y
            )

        # Remover NPC de escena antes de dropear (libera el tile ocupado)
        await self._remove_npc_from_game(npc)

        # Dropear oro si el NPC tiene
        if npc.gold_min > 0 or npc.gold_max > 0:
            await self._drop_gold(npc)

        # Dropear items según loot table
        if self.loot_table_service and self.item_catalog:
            await self._drop_loot(npc)

        # Eliminar datos del NPC en Redis
        await self.npc_repo.remove_npc(npc.instance_id)

        # Notificar a random_spawn_service si es un NPC random
        if self.random_spawn_service:
            await self.random_spawn_service.on_random_npc_death(npc.instance_id)

        # Programar respawn
        if self.npc_respawn_service:
            await self.npc_respawn_service.schedule_respawn(npc)

        logger.info(
            "NPC %s (CharIndex: %d) eliminado tras ser matado por user_id %d (%s)",
            npc.name,
            npc.char_index,
            killer_user_id,
            death_reason,
        )

    async def _give_experience(
        self, user_id: int, experience: int, message_sender: MessageSender, npc: NPC
    ) -> None:
        """Otorga experiencia al jugador o distribuye a party si está en una.

        Args:
            user_id: ID del jugador que mató al NPC.
            experience: Cantidad de experiencia total.
            message_sender: MessageSender del jugador.
            npc: NPC que fue matado (para obtener posición).
        """
        return await self._experience.give_experience(user_id, experience, message_sender, npc)

    async def _distribute_party_experience(
        self, user_id: int, experience: int, npc: NPC, party: Party
    ) -> None:
        """Distribuye experiencia a todos los miembros de la party.

        Args:
            user_id: ID del jugador que mató al NPC.
            experience: Cantidad de experiencia total.
            npc: NPC que fue matado.
            party: Objeto Party con los miembros.
        """
        return await self._experience.distribute_party_experience(user_id, experience, npc, party)

    async def _update_member_experience(
        self, member_id: int, exp_amount: float, killer_id: int, npc: NPC, total_exp: int
    ) -> None:
        """Actualiza la experiencia de un miembro de party.

        Args:
            member_id: ID del miembro.
            exp_amount: Cantidad de experiencia recibida.
            killer_id: ID del jugador que mató al NPC.
            npc: NPC que fue matado.
            total_exp: Experiencia total ganada.
        """
        return await self._experience.update_member_experience(
            member_id, exp_amount, killer_id, npc, total_exp
        )

    async def _notify_party_kill(self, party: Party, killer_id: int, npc: NPC) -> None:
        """Notifica a todos los miembros de party sobre un kill.

        Args:
            party: Objeto Party con los miembros.
            killer_id: ID del jugador que mató al NPC.
            npc: NPC que fue matado.
        """
        return await self._experience.notify_party_kill(party, killer_id, npc)

    async def _give_solo_experience(
        self, user_id: int, experience: int, message_sender: MessageSender
    ) -> None:
        """Otorga experiencia a un jugador que no está en party.

        Args:
            user_id: ID del jugador.
            experience: Cantidad de experiencia.
            message_sender: MessageSender del jugador.
        """
        return await self._experience.give_solo_experience(user_id, experience, message_sender)

    async def _drop_gold(self, npc: NPC) -> None:
        """Dropea oro del NPC en el suelo.

        Args:
            npc: NPC que murió.
        """
        import random  # ruff: ignore[import-outside-top-level]

        gold_amount = random.randint(npc.gold_min, npc.gold_max)
        if gold_amount <= 0:
            return

        # Buscar posición libre
        drop_pos = self._find_free_position_for_drop(npc.map_id, npc.x, npc.y)
        if not drop_pos:
            logger.warning(
                "No se encontró posición libre para dropear oro cerca de (%d,%d)",
                npc.x,
                npc.y,
            )
            return

        drop_x, drop_y = drop_pos

        # El loot siempre es público - cualquiera puede recogerlo
        # Crear ground item de oro
        gold_item: dict[str, int | str | None] = {
            "item_id": 12,  # ID del oro
            "quantity": gold_amount,
            "grh_index": 511,  # GrhIndex del oro
            "owner_id": None,  # None = cualquiera puede recoger
            "spawn_time": None,
        }

        if not await self.map_manager.add_ground_item_committed(
            map_id=npc.map_id,
            x=drop_x,
            y=drop_y,
            item=gold_item,
            broadcast_service=self.broadcast_service,
        ):
            return

        logger.info(
            "Dropeado %d oro en (%d,%d) por muerte de %s", gold_amount, drop_x, drop_y, npc.name
        )

    async def _drop_loot(self, npc: NPC) -> None:
        """Dropea items del NPC según su loot table.

        Args:
            npc: NPC que murió.
        """
        if not self.loot_table_service or not self.item_catalog:
            return

        loot = self.loot_table_service.get_loot_for_npc(npc.npc_id)

        # El loot siempre es público - cualquiera puede recogerlo
        for item_id, quantity in loot:
            # Obtener GrhIndex del catálogo
            grh_index = self.item_catalog.get_grh_index(item_id)
            if grh_index is None:
                logger.warning("Item %d no tiene GrhIndex en el catálogo", item_id)
                continue

            # Buscar posición libre
            drop_pos = self._find_free_position_for_drop(npc.map_id, npc.x, npc.y)
            if not drop_pos:
                logger.warning(
                    "No se encontró posición libre para dropear %s cerca de (%d,%d)",
                    self.item_catalog.get_item_name(item_id),
                    npc.x,
                    npc.y,
                )
                continue

            drop_x, drop_y = drop_pos

            # Crear ground item
            item: dict[str, int | str | None] = {
                "item_id": item_id,
                "grh_index": grh_index,
                "quantity": quantity,
                "owner_id": None,  # None = cualquiera puede recoger
                "spawn_time": None,
            }

            if not await self.map_manager.add_ground_item_committed(
                map_id=npc.map_id,
                x=drop_x,
                y=drop_y,
                item=item,
                broadcast_service=self.broadcast_service,
            ):
                continue

            logger.info(
                "Dropeado item %s (x%d) en (%d,%d) por muerte de %s",
                self.item_catalog.get_item_name(item_id),
                quantity,
                drop_x,
                drop_y,
                npc.name,
            )

    async def _remove_npc_from_game(self, npc: NPC) -> None:
        """Elimina completamente un NPC del juego.

        Args:
            npc: NPC a eliminar.
        """
        # Enviar efecto visual de muerte si el NPC lo tiene configurado
        if npc.fx > 0:
            await self.broadcast_service.broadcast_create_fx(
                map_id=npc.map_id,
                char_index=npc.char_index,
                fx=npc.fx,
                loops=1,  # One-shot: reproducir una sola vez
            )
            logger.debug(
                "FX de muerte enviado para %s: fx=%d en (%d,%d)",
                npc.name,
                npc.fx,
                npc.x,
                npc.y,
            )

        # Remover del MapManager
        self.map_manager.remove_npc(npc.map_id, npc.instance_id)

        # Broadcast CHARACTER_REMOVE a todos los jugadores
        await self.broadcast_service.broadcast_character_remove(
            map_id=npc.map_id,
            char_index=npc.char_index,
        )

    async def _check_and_handle_level_up(
        self,
        user_id: int,
        _current_level: int,
        _new_experience: int,
        message_sender: MessageSender,
    ) -> None:
        """Confirma crecimiento y puntos desde el estado Redis más reciente."""
        return await self._experience.check_and_handle_level_up(
            user_id, _current_level, _new_experience, message_sender
        )

    def _find_free_position_for_drop(
        self, map_id: int, center_x: int, center_y: int, radius: int = 4, max_attempts: int = 40
    ) -> tuple[int, int] | None:
        """Busca una posición libre cercana para dropear un item.

        Args:
            map_id: ID del mapa.
            center_x: Coordenada X central.
            center_y: Coordenada Y central.
            radius: Radio de búsqueda.
            max_attempts: Cantidad máxima de intentos aleatorios para encontrar una posición.

        Returns:
            Tupla (x, y) con una posición libre y no bloqueada, o None si no encuentra.
        """
        import random  # ruff: ignore[import-outside-top-level]

        # Intentar primero la posición central
        if self._is_valid_drop_position(map_id, center_x, center_y):
            return (center_x, center_y)

        # Buscar en posiciones cercanas
        for _ in range(max_attempts):
            offset_x = random.randint(-radius, radius)
            offset_y = random.randint(-radius, radius)

            x = center_x + offset_x
            y = center_y + offset_y

            # Verificar que sea posición válida
            if self._is_valid_drop_position(map_id, x, y):
                return (x, y)

        return None

    def _is_valid_drop_position(self, map_id: int, x: int, y: int) -> bool:
        """Verifica si una posición es válida para dropear items.

        Args:
            map_id: ID del mapa.
            x: Coordenada X.
            y: Coordenada Y.

        Returns:
            True si la posición es válida para dropear.
        """
        # Verificar que no haya items en esa posición
        items = self.map_manager.get_ground_items(map_id, x, y)
        if items:
            return False

        # Verificar que no haya un jugador o NPC ocupando el tile
        if self.map_manager.is_tile_occupied(map_id, x, y):
            return False

        # Verificar que la casilla no esté bloqueada (paredes, agua, etc.)
        return self.map_manager.can_move_to(map_id, x, y)
