"""Handler especializado para manejo de loot drop después de muerte de NPC."""

import logging
import random
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.game.map_manager import MapManager
    from src.messaging.message_sender import MessageSender
    from src.models.item_catalog import ItemCatalog
    from src.models.npc import NPC
    from src.services.multiplayer_broadcast_service import MultiplayerBroadcastService
    from src.services.npc.loot_table_service import LootTableService
else:
    NPC = object  # Para type hints en runtime

logger = logging.getLogger(__name__)


class AttackLootHandler:
    """Handler especializado para manejo de loot drop."""

    def __init__(
        self,
        map_manager: MapManager,
        loot_table_service: LootTableService | None,
        item_catalog: ItemCatalog | None,
        broadcast_service: MultiplayerBroadcastService | None,
        message_sender: MessageSender,
    ) -> None:
        """Inicializa el handler de loot.

        Args:
            map_manager: Gestor de mapas.
            loot_table_service: Servicio de loot tables.
            item_catalog: Catálogo de items.
            broadcast_service: Servicio de broadcast.
            message_sender: Enviador de mensajes.
        """
        self.map_manager = map_manager
        self.loot_table_service = loot_table_service
        self.item_catalog = item_catalog
        self.broadcast_service = broadcast_service
        self.message_sender = message_sender

    async def handle_loot_drop(self, npc: NPC) -> None:
        """Maneja el drop de loot cuando un NPC muere.

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

            logger.debug(
                "Dropeando item_id=%d grh_index=%d quantity=%d",
                item_id,
                grh_index,
                quantity,
            )

            # Buscar posición libre cercana para dropear el item
            drop_pos = self._find_free_position_for_drop(npc.map_id, npc.x, npc.y, radius=2)

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
            ground_item: dict[str, int | str | None] = {
                "item_id": item_id,
                "quantity": quantity,
                "grh_index": grh_index,
                "owner_id": None,
                "spawn_time": None,
            }

            # Agregar al MapManager
            self.map_manager.add_ground_item(
                map_id=npc.map_id, x=drop_x, y=drop_y, item=ground_item
            )

            # Broadcast OBJECT_CREATE a jugadores cercanos
            if self.broadcast_service:
                await self.broadcast_service.broadcast_object_create(
                    map_id=npc.map_id,
                    x=drop_x,
                    y=drop_y,
                    grh_index=grh_index,
                )

            item_name = self.item_catalog.get_item_name(item_id) or f"Item {item_id}"
            logger.info(
                "NPC %s dropeó %dx %s en (%d, %d)",
                npc.name,
                quantity,
                item_name,
                drop_x,
                drop_y,
            )

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
            Tupla (x, y) con una posición libre, o None si no encuentra.
        """
        # Intentar primero la posición central
        if self._is_valid_drop_position(map_id, center_x, center_y):
            return (center_x, center_y)

        # Buscar en posiciones cercanas
        for _ in range(20):  # Máximo 20 intentos
            offset_x = random.randint(-radius, radius)
            offset_y = random.randint(-radius, radius)

            # Saltar la posición central (ya la verificamos antes)
            if offset_x == 0 and offset_y == 0:
                continue

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
        if not self.map_manager:
            return False

        # Verificar límites del mapa
        if x < 1 or x > 100 or y < 1 or y > 100:  # noqa: PLR2004
            return False

        # Verificar que no haya items en esa posición
        items = self.map_manager.get_ground_items(map_id, x, y)
        if items:
            return False

        # Verificar que no haya un jugador o NPC ocupando el tile
        if self.map_manager.is_tile_occupied(map_id, x, y):
            return False

        # Verificar que la casilla no esté bloqueada (paredes, agua, etc.)
        return self.map_manager.can_move_to(map_id, x, y)
