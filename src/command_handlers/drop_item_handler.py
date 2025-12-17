"""Handler especializado para drop de items del inventario."""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.game.map_manager import MapManager
    from src.messaging.message_sender import MessageSender
    from src.models.item_catalog import ItemCatalog
    from src.repositories.inventory_repository import InventoryRepository
    from src.repositories.player_repository import PlayerRepository
    from src.services.multiplayer_broadcast_service import MultiplayerBroadcastService

logger = logging.getLogger(__name__)


class DropItemHandler:
    """Handler especializado para drop de items del inventario."""

    def __init__(
        self,
        player_repo: PlayerRepository,
        inventory_repo: InventoryRepository | None,
        map_manager: MapManager,
        broadcast_service: MultiplayerBroadcastService | None,
        message_sender: MessageSender,
        item_catalog: ItemCatalog | None = None,
    ) -> None:
        """Inicializa el handler de items.

        Args:
            player_repo: Repositorio de jugadores.
            inventory_repo: Repositorio de inventario.
            map_manager: Gestor de mapas.
            broadcast_service: Servicio de broadcast.
            message_sender: Enviador de mensajes.
            item_catalog: Catálogo de items para obtener datos gráficos.
        """
        self.player_repo = player_repo
        self.inventory_repo = inventory_repo
        self.map_manager = map_manager
        self.broadcast_service = broadcast_service
        self.message_sender = message_sender
        self.item_catalog = item_catalog

    async def drop_item(
        self, user_id: int, slot: int, quantity: int
    ) -> tuple[bool, str | None, dict[str, int | str] | None]:
        """Tira un item del inventario al suelo.

        Args:
            user_id: ID del jugador.
            slot: Número de slot del inventario (1-30).
            quantity: Cantidad a tirar.

        Returns:
            Tupla (success, error_message, result_data).
        """
        if not self.inventory_repo:
            return False, "Repositorio de inventario no disponible", None

        # Obtener item del slot
        slot_data = await self.inventory_repo.get_slot(user_id, slot)
        if not slot_data:
            await self.message_sender.send_console_msg("No hay nada en ese slot.")
            return False, "Slot vacío", None

        item_id, current_quantity = slot_data

        # Validar cantidad
        if quantity <= 0:
            await self.message_sender.send_console_msg("Cantidad inválida.")
            return False, "Cantidad inválida", None

        # Ajustar cantidad al mínimo entre lo que tiene y lo que quiere tirar
        actual_quantity = min(quantity, current_quantity)

        # Obtener posición del jugador
        position = await self.player_repo.get_position(user_id)
        if not position:
            return False, "No se pudo obtener la posición del jugador", None

        map_id = position["map"]
        x = position["x"]
        y = position["y"]

        # Obtener datos del item para el gráfico
        grh_index = self._get_item_grh_index(item_id)
        item_name = self._get_item_name(item_id)

        # Actualizar inventario
        new_quantity = current_quantity - actual_quantity
        if new_quantity > 0:
            # Reducir cantidad en el slot
            await self.inventory_repo.set_slot(user_id, slot, item_id, new_quantity)
        else:
            # Vaciar el slot completamente
            await self.inventory_repo.clear_slot(user_id, slot)

        # Notificar al cliente del cambio en el inventario
        await self.message_sender.send_change_inventory_slot(
            slot=slot,
            item_id=item_id if new_quantity > 0 else 0,
            name=item_name if new_quantity > 0 else "",
            amount=new_quantity,
            equipped=False,
            grh_id=grh_index if new_quantity > 0 else 0,
            item_type=0,  # No necesario para actualización
            max_hit=0,
            min_hit=0,
            max_def=0,
            min_def=0,
        )

        # Crear ground item
        ground_item: dict[str, int | str | None] = {
            "item_id": item_id,
            "quantity": actual_quantity,
            "grh_index": grh_index,
            "owner_id": None,
            "spawn_time": None,
        }

        # Agregar al MapManager
        self.map_manager.add_ground_item(map_id=map_id, x=x, y=y, item=ground_item)

        # Broadcast OBJECT_CREATE a jugadores cercanos
        if self.broadcast_service:
            await self.broadcast_service.broadcast_object_create(
                map_id=map_id, x=x, y=y, grh_index=grh_index
            )

        # Notificar al jugador
        if actual_quantity > 1:
            await self.message_sender.send_console_msg(
                f"Tiraste {actual_quantity} {item_name} al suelo."
            )
        else:
            await self.message_sender.send_console_msg(f"Tiraste {item_name} al suelo.")

        logger.info(
            "Jugador %d tiró %d x item %d (%s) en (%d,%d)",
            user_id,
            actual_quantity,
            item_id,
            item_name,
            x,
            y,
        )

        return (
            True,
            None,
            {"item_id": item_id, "quantity": actual_quantity, "type": "item"},
        )

    def _get_item_grh_index(self, item_id: int) -> int:
        """Obtiene el índice gráfico de un item.

        Args:
            item_id: ID del item.

        Returns:
            GrhIndex del item o un valor por defecto.
        """
        if self.item_catalog:
            grh = self.item_catalog.get_grh_index(item_id)
            if grh:
                return grh
        # Fallback: usar el item_id como grh_index (común en AO)
        return item_id

    def _get_item_name(self, item_id: int) -> str:
        """Obtiene el nombre de un item.

        Args:
            item_id: ID del item.

        Returns:
            Nombre del item o "Item desconocido".
        """
        if self.item_catalog:
            name = self.item_catalog.get_item_name(item_id)
            if name:
                return name
        return f"Item #{item_id}"
