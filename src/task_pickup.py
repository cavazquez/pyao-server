"""Task para manejar recogida de items del suelo."""

import logging
from typing import TYPE_CHECKING

from src.item_constants import GOLD_ITEM_ID
from src.session_manager import SessionManager
from src.task import Task

if TYPE_CHECKING:
    from src.inventory_repository import InventoryRepository
    from src.map_manager import MapManager
    from src.message_sender import MessageSender
    from src.multiplayer_broadcast_service import MultiplayerBroadcastService
    from src.player_repository import PlayerRepository

logger = logging.getLogger(__name__)


class TaskPickup(Task):
    """Maneja el packet PICKUP del cliente."""

    def __init__(
        self,
        data: bytes,
        message_sender: MessageSender,
        player_repo: PlayerRepository | None = None,
        inventory_repo: InventoryRepository | None = None,
        map_manager: MapManager | None = None,
        broadcast_service: MultiplayerBroadcastService | None = None,
        session_data: dict[str, dict[str, int]] | None = None,
    ) -> None:
        """Inicializa el task.

        Args:
            data: Datos del packet.
            message_sender: Enviador de mensajes.
            player_repo: Repositorio de jugadores.
            inventory_repo: Repositorio de inventario.
            map_manager: Gestor de mapas.
            broadcast_service: Servicio de broadcast.
            session_data: Datos de sesión.
        """
        super().__init__(data, message_sender)
        self.player_repo = player_repo
        self.inventory_repo = inventory_repo
        self.map_manager = map_manager
        self.broadcast_service = broadcast_service
        self.session_data = session_data or {}

    async def execute(self) -> None:
        """Procesa la recogida de un item del suelo."""
        # Obtener user_id de la sesión
        user_id = SessionManager.get_user_id(self.session_data)
        if user_id is None:
            logger.warning("Intento de recoger item sin estar logueado")
            return

        logger.info("TaskPickup: user_id=%d intentando recoger item", user_id)

        # Validar que tenemos los servicios necesarios
        if not self.player_repo or not self.map_manager:
            logger.error("TaskPickup: Faltan servicios necesarios")
            return

        # Obtener posición del jugador
        position = await self.player_repo.get_position(user_id)
        if not position:
            logger.error("No se pudo obtener posición del jugador %d", user_id)
            return

        map_id = position["map"]
        x = position["x"]
        y = position["y"]

        # Buscar items en ese tile
        items = self.map_manager.get_ground_items(map_id, x, y)

        if not items:
            await self.message_sender.send_console_msg("No hay nada aquí.")
            logger.debug("Jugador %d intentó recoger pero no hay items en (%d,%d)", user_id, x, y)
            return

        # Recoger primer item
        item = items[0]
        item_id = item.get("item_id")
        quantity = item.get("quantity", 1)

        # Validar tipos
        if not isinstance(quantity, int):
            quantity = 1
        if not isinstance(item_id, int) and item_id is not None:
            logger.warning("item_id inválido: %s", item_id)
            return

        # Manejar oro especialmente
        if item_id == GOLD_ITEM_ID:
            await self._pickup_gold(user_id, quantity, map_id, x, y)
        else:
            await self._pickup_item(user_id, item_id, quantity, map_id, x, y)

    async def _pickup_gold(self, user_id: int, gold: int, map_id: int, x: int, y: int) -> None:
        """Recoge oro del suelo.

        Args:
            user_id: ID del jugador.
            gold: Cantidad de oro.
            map_id: ID del mapa.
            x: Posición X.
            y: Posición Y.
        """
        if not self.player_repo:
            return

        # Obtener oro actual
        stats = await self.player_repo.get_stats(user_id)
        if not stats:
            return

        current_gold = stats.get("gold", 0)
        new_gold = current_gold + gold

        # Actualizar oro
        await self.player_repo.update_gold(user_id, new_gold)

        # Remover del suelo
        if self.map_manager:
            self.map_manager.remove_ground_item(map_id, x, y, item_index=0)

        # Broadcast OBJECT_DELETE
        if self.broadcast_service:
            await self.broadcast_service.broadcast_object_delete(map_id, x, y)

        # Notificar al jugador
        await self.message_sender.send_console_msg(f"Recogiste {gold} monedas de oro.")
        logger.info("Jugador %d recogió %d de oro en (%d,%d)", user_id, gold, x, y)

    async def _pickup_item(
        self, user_id: int, item_id: int | None, quantity: int, map_id: int, x: int, y: int
    ) -> None:
        """Recoge un item del suelo.

        Args:
            user_id: ID del jugador.
            item_id: ID del item.
            quantity: Cantidad.
            map_id: ID del mapa.
            x: Posición X.
            y: Posición Y.
        """
        if not self.inventory_repo or not item_id:
            return

        # TODO: Validar que el inventario no esté lleno
        # TODO: Agregar item al inventario
        # TODO: Enviar CHANGE_INVENTORY_SLOT

        # Por ahora solo mostramos mensaje
        await self.message_sender.send_console_msg(
            f"Recogiste un item (ID: {item_id}, cantidad: {quantity})."
        )

        # Remover del suelo
        if self.map_manager:
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
