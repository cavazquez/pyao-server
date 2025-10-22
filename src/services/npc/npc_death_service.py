"""Servicio para manejar la muerte de NPCs."""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.item_catalog import ItemCatalog
    from src.services.npc.loot_table_service import LootTableService
    from src.map_manager import MapManager
    from src.messaging.message_sender import MessageSender
    from src.services.multiplayer_broadcast_service import MultiplayerBroadcastService
    from src.models.npc import NPC
    from src.repositories.npc_repository import NPCRepository
    from src.services.npc.npc_respawn_service import NPCRespawnService
    from src.repositories.player_repository import PlayerRepository

logger = logging.getLogger(__name__)


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
        """
        self.map_manager = map_manager
        self.npc_repo = npc_repo
        self.player_repo = player_repo
        self.broadcast_service = broadcast_service
        self.loot_table_service = loot_table_service
        self.item_catalog = item_catalog
        self.npc_respawn_service = npc_respawn_service

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
        # Mensaje de muerte
        await message_sender.send_console_msg(
            f"¡Has matado a {npc.name}! Ganaste {experience} EXP."
        )

        # Dar experiencia al jugador
        await self._give_experience(killer_user_id, experience, message_sender)

        # Dropear oro si el NPC tiene
        if npc.gold_min > 0 or npc.gold_max > 0:
            await self._drop_gold(npc)

        # Dropear items según loot table
        if self.loot_table_service and self.item_catalog:
            await self._drop_loot(npc)

        # Remover NPC del juego
        await self._remove_npc_from_game(npc)

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
        self, user_id: int, experience: int, message_sender: MessageSender
    ) -> None:
        """Otorga experiencia al jugador.

        Args:
            user_id: ID del jugador.
            experience: Cantidad de experiencia.
            message_sender: MessageSender del jugador.
        """
        stats = await self.player_repo.get_stats(user_id)
        if not stats:
            return

        current_exp = stats.get("exp", 0)
        new_exp = current_exp + experience

        await self.player_repo.update_experience(user_id, new_exp)
        await message_sender.send_update_exp(new_exp)

        logger.info("Jugador %d ganó %d de experiencia (total: %d)", user_id, experience, new_exp)

    async def _drop_gold(self, npc: NPC) -> None:
        """Dropea oro del NPC en el suelo.

        Args:
            npc: NPC que murió.
        """
        import random  # noqa: PLC0415

        gold_amount = random.randint(npc.gold_min, npc.gold_max)  # noqa: S311
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

        # Crear ground item de oro
        gold_item: dict[str, int | str | None] = {
            "item_id": 12,  # ID del oro
            "quantity": gold_amount,
            "grh_index": 511,  # GrhIndex del oro
            "owner_id": None,
            "spawn_time": None,
        }

        # Agregar al mapa
        self.map_manager.add_ground_item(map_id=npc.map_id, x=drop_x, y=drop_y, item=gold_item)

        # Broadcast a todos los jugadores
        await self.broadcast_service.broadcast_object_create(
            map_id=npc.map_id,
            x=drop_x,
            y=drop_y,
            grh_index=511,
        )

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
                "owner_id": None,
                "spawn_time": None,
            }

            # Agregar al mapa
            self.map_manager.add_ground_item(map_id=npc.map_id, x=drop_x, y=drop_y, item=item)

            # Broadcast a todos los jugadores
            await self.broadcast_service.broadcast_object_create(
                map_id=npc.map_id,
                x=drop_x,
                y=drop_y,
                grh_index=grh_index,
            )

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
        self.map_manager.remove_npc(npc.map_id, str(npc.char_index))

        # Broadcast CHARACTER_REMOVE a todos los jugadores
        await self.broadcast_service.broadcast_character_remove(
            map_id=npc.map_id,
            char_index=npc.char_index,
        )

        # Eliminar de Redis
        await self.npc_repo.remove_npc(npc.instance_id)

    def _find_free_position_for_drop(
        self, map_id: int, center_x: int, center_y: int, radius: int = 2
    ) -> tuple[int, int] | None:
        """Busca una posición libre cercana para dropear un item.

        Args:
            map_id: ID del mapa.
            center_x: Coordenada X central.
            center_y: Coordenada Y central.
            radius: Radio de búsqueda.

        Returns:
            Tupla (x, y) con una posición libre y no bloqueada, o None si no encuentra.
        """
        import random  # noqa: PLC0415

        # Intentar primero la posición central
        if self._is_valid_drop_position(map_id, center_x, center_y):
            return (center_x, center_y)

        # Buscar en posiciones cercanas
        for _ in range(20):  # Máximo 20 intentos
            offset_x = random.randint(-radius, radius)  # noqa: S311
            offset_y = random.randint(-radius, radius)  # noqa: S311

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

        # Verificar que la casilla no esté bloqueada
        return self.map_manager.can_move_to(map_id, x, y)
