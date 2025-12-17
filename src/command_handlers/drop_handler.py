"""Handler para comando de soltar item."""

import logging
from typing import TYPE_CHECKING

from src.commands.base import Command, CommandHandler, CommandResult
from src.commands.drop_command import DropCommand

# Constantes para el oro
GOLD_ITEM_ID = 12  # ID del item oro en el catálogo
GOLD_GRH_INDEX = 511  # Índice gráfico del oro

# Slots especiales para oro
# - slot=0: formato original/VB6
# - slot=31: formato cliente Godot (Flagoro)
GOLD_SLOT_CLASSIC = 0
GOLD_SLOT_GODOT = 31  # Consts.Flagoro en el cliente Godot

if TYPE_CHECKING:
    from src.game.map_manager import MapManager
    from src.messaging.message_sender import MessageSender
    from src.models.item_catalog import ItemCatalog
    from src.repositories.inventory_repository import InventoryRepository
    from src.repositories.player_repository import PlayerRepository
    from src.services.multiplayer_broadcast_service import MultiplayerBroadcastService

logger = logging.getLogger(__name__)


class DropCommandHandler(CommandHandler):
    """Handler para comando de soltar item (solo lógica de negocio)."""

    def __init__(
        self,
        player_repo: PlayerRepository,
        inventory_repo: InventoryRepository | None,
        map_manager: MapManager,
        broadcast_service: MultiplayerBroadcastService | None,
        message_sender: MessageSender,
        item_catalog: ItemCatalog | None = None,
    ) -> None:
        """Inicializa el handler.

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

    async def handle(self, command: Command) -> CommandResult:
        """Ejecuta el comando de soltar item (solo lógica de negocio).

        Args:
            command: Comando de soltar item.

        Returns:
            Resultado de la ejecución.
        """
        if not isinstance(command, DropCommand):
            return CommandResult.error("Comando inválido: se esperaba DropCommand")

        user_id = command.user_id
        slot = command.slot
        quantity = command.quantity

        logger.info("DropCommandHandler: user_id=%d slot=%d quantity=%d", user_id, slot, quantity)

        # Slots especiales de oro:
        # - slot <= 0: formato original/VB6
        # - slot = 31: formato cliente Godot (Flagoro)
        if slot <= GOLD_SLOT_CLASSIC or slot == GOLD_SLOT_GODOT:
            return await self._drop_gold(user_id, quantity)

        return await self._drop_item(user_id, slot, quantity)

    async def _drop_gold(self, user_id: int, quantity: int) -> CommandResult:
        """Tira oro del jugador al suelo.

        Args:
            user_id: ID del jugador.
            quantity: Cantidad de oro a tirar.

        Returns:
            Resultado de la ejecución.
        """
        # Obtener oro actual del jugador
        current_gold = await self.player_repo.get_gold(user_id)

        # Validar cantidad
        if quantity <= 0:
            await self.message_sender.send_console_msg("Cantidad inválida.")
            return CommandResult.error("Cantidad inválida")

        # Ajustar cantidad al mínimo entre lo que tiene y lo que quiere tirar
        actual_quantity = min(quantity, current_gold)

        if actual_quantity == 0:
            await self.message_sender.send_console_msg("No tienes oro para tirar.")
            return CommandResult.error("No tienes oro para tirar")

        # Obtener posición del jugador
        position = await self.player_repo.get_position(user_id)
        if not position:
            return CommandResult.error("No se pudo obtener la posición del jugador")

        map_id = position["map"]
        x = position["x"]
        y = position["y"]

        # Reducir oro del jugador
        new_gold = current_gold - actual_quantity
        await self.player_repo.update_gold(user_id, new_gold)

        # Enviar UPDATE_USER_STATS al cliente para actualizar GUI
        # Nota: new_gold ya está actualizado en el repositorio
        await self.message_sender.send_update_user_stats_from_repo(user_id, self.player_repo)

        # Crear ground item
        ground_item: dict[str, int | str | None] = {
            "item_id": GOLD_ITEM_ID,
            "quantity": actual_quantity,
            "grh_index": GOLD_GRH_INDEX,
            "owner_id": None,
            "spawn_time": None,
        }

        # Agregar al MapManager
        self.map_manager.add_ground_item(map_id=map_id, x=x, y=y, item=ground_item)

        # Broadcast OBJECT_CREATE a jugadores cercanos
        if self.broadcast_service:
            await self.broadcast_service.broadcast_object_create(
                map_id=map_id, x=x, y=y, grh_index=GOLD_GRH_INDEX
            )

        # Notificar al jugador
        await self.message_sender.send_console_msg(
            f"Tiraste {actual_quantity} monedas de oro al suelo."
        )
        logger.info("Jugador %d tiró %d de oro en (%d,%d)", user_id, actual_quantity, x, y)

        return CommandResult.ok(
            data={"item_id": GOLD_ITEM_ID, "quantity": actual_quantity, "type": "gold"}
        )

    async def _drop_item(self, user_id: int, slot: int, quantity: int) -> CommandResult:
        """Tira un item del inventario al suelo.

        Args:
            user_id: ID del jugador.
            slot: Número de slot del inventario (1-30).
            quantity: Cantidad a tirar.

        Returns:
            Resultado de la ejecución.
        """
        if not self.inventory_repo:
            return CommandResult.error("Repositorio de inventario no disponible")

        # Obtener item del slot
        slot_data = await self.inventory_repo.get_slot(user_id, slot)
        if not slot_data:
            await self.message_sender.send_console_msg("No hay nada en ese slot.")
            return CommandResult.error("Slot vacío")

        item_id, current_quantity = slot_data

        # Validar cantidad
        if quantity <= 0:
            await self.message_sender.send_console_msg("Cantidad inválida.")
            return CommandResult.error("Cantidad inválida")

        # Ajustar cantidad al mínimo entre lo que tiene y lo que quiere tirar
        actual_quantity = min(quantity, current_quantity)

        # Obtener posición del jugador
        position = await self.player_repo.get_position(user_id)
        if not position:
            return CommandResult.error("No se pudo obtener la posición del jugador")

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

        return CommandResult.ok(
            data={"item_id": item_id, "quantity": actual_quantity, "type": "item"}
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
