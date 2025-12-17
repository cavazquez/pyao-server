"""Handler especializado para pickup de items del inventario."""

import logging
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from src.game.map_manager import MapManager
    from src.messaging.message_sender import MessageSender
    from src.models.item_catalog import ItemCatalog
    from src.repositories.inventory_repository import InventoryRepository
    from src.repositories.player_repository import PlayerRepository
    from src.services.multiplayer_broadcast_service import MultiplayerBroadcastService

logger = logging.getLogger(__name__)


class PickupItemHandler:
    """Handler especializado para pickup de items del inventario."""

    def __init__(
        self,
        player_repo: PlayerRepository,
        inventory_repo: InventoryRepository | None,
        map_manager: MapManager,
        broadcast_service: MultiplayerBroadcastService | None,
        item_catalog: ItemCatalog | None,
        message_sender: MessageSender,
    ) -> None:
        """Inicializa el handler de items.

        Args:
            player_repo: Repositorio de jugadores.
            inventory_repo: Repositorio de inventario.
            map_manager: Gestor de mapas.
            broadcast_service: Servicio de broadcast.
            item_catalog: Catálogo de items.
            message_sender: Enviador de mensajes.
        """
        self.player_repo = player_repo
        self.inventory_repo = inventory_repo
        self.map_manager = map_manager
        self.broadcast_service = broadcast_service
        self.item_catalog = item_catalog
        self.message_sender = message_sender

    async def pickup_item(
        self, user_id: int, item_id: int | None, quantity: int, map_id: int, x: int, y: int
    ) -> tuple[bool, str | None, dict[str, int | str | list[tuple[int, int]]] | None]:
        """Recoge un item del suelo.

        Args:
            user_id: ID del jugador.
            item_id: ID del item.
            quantity: Cantidad.
            map_id: ID del mapa.
            x: Posición X.
            y: Posición Y.

        Returns:
            Tupla (success, error_message, result_data).
        """
        if not self.inventory_repo or not item_id or not self.item_catalog:
            return False, "Servicios no disponibles para recoger item", None

        # Obtener datos del item del catálogo
        item_data = self.item_catalog.get_item_data(item_id)
        if not item_data:
            logger.warning("Item %d no encontrado en el catálogo", item_id)
            return False, f"Item {item_id} no encontrado en el catálogo", None

        # Agregar item al inventario
        modified_slots = await self.inventory_repo.add_item(user_id, item_id, quantity)

        if not modified_slots:
            await self.message_sender.send_console_msg("Tu inventario está lleno.")
            return False, "Inventario lleno", None

        # Enviar CHANGE_INVENTORY_SLOT para todos los slots modificados
        for slot, slot_quantity in modified_slots:
            await self.message_sender.send_change_inventory_slot(
                slot=slot,
                item_id=item_id,
                name=str(item_data.get("Name", "Item")),
                amount=slot_quantity,
                equipped=False,
                grh_id=cast("int", item_data.get("GrhIndex", 0)),
                item_type=cast("int", item_data.get("ObjType", 0)),
                max_hit=cast("int", item_data.get("MaxHit", 0)),
                min_hit=cast("int", item_data.get("MinHit", 0)),
                max_def=cast("int", item_data.get("MaxDef", 0)),
                min_def=cast("int", item_data.get("MinDef", 0)),
                sale_price=cast("float", item_data.get("Valor", 0)),
            )

        # Notificar al jugador
        item_name = item_data.get("Name", f"Item {item_id}")
        await self.message_sender.send_console_msg(f"Recogiste {quantity}x {item_name}.")

        # Remover del suelo
        self.map_manager.remove_ground_item(map_id, x, y, item_index=0)

        # Broadcast OBJECT_DELETE
        if self.broadcast_service:
            await self.broadcast_service.broadcast_object_delete(map_id, x, y)

        logger.info(
            "Jugador %d recogió item %d (cantidad: %d) en (%d,%d)",
            user_id,
            item_id,
            quantity,
            x,
            y,
        )

        return (
            True,
            None,
            {"item_id": item_id, "quantity": quantity, "type": "item", "slots": modified_slots},
        )
