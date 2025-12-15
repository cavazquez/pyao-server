"""Handler para comando de recoger item."""

import logging
from typing import TYPE_CHECKING, cast

from src.commands.base import Command, CommandHandler, CommandResult
from src.commands.pickup_command import PickupCommand
from src.models.item_constants import GOLD_ITEM_ID

if TYPE_CHECKING:
    from src.game.map_manager import MapManager
    from src.messaging.message_sender import MessageSender
    from src.models.item_catalog import ItemCatalog
    from src.repositories.inventory_repository import InventoryRepository
    from src.repositories.player_repository import PlayerRepository
    from src.services.multiplayer_broadcast_service import MultiplayerBroadcastService
    from src.services.party_service import PartyService

logger = logging.getLogger(__name__)


class PickupCommandHandler(CommandHandler):
    """Handler para comando de recoger item (solo lógica de negocio)."""

    def __init__(
        self,
        player_repo: PlayerRepository,
        inventory_repo: InventoryRepository | None,
        map_manager: MapManager,
        broadcast_service: MultiplayerBroadcastService | None,
        item_catalog: ItemCatalog | None,
        party_service: PartyService | None,
        message_sender: MessageSender,
    ) -> None:
        """Inicializa el handler.

        Args:
            player_repo: Repositorio de jugadores.
            inventory_repo: Repositorio de inventario.
            map_manager: Gestor de mapas.
            broadcast_service: Servicio de broadcast.
            item_catalog: Catálogo de items.
            party_service: Servicio de parties (para loot compartido).
            message_sender: Enviador de mensajes.
        """
        self.player_repo = player_repo
        self.inventory_repo = inventory_repo
        self.map_manager = map_manager
        self.broadcast_service = broadcast_service
        self.item_catalog = item_catalog
        self.party_service = party_service
        self.message_sender = message_sender

    async def handle(self, command: Command) -> CommandResult:
        """Ejecuta el comando de recoger item (solo lógica de negocio).

        Args:
            command: Comando de recoger item.

        Returns:
            Resultado de la ejecución.
        """
        if not isinstance(command, PickupCommand):
            return CommandResult.error("Comando inválido: se esperaba PickupCommand")

        user_id = command.user_id

        logger.info("PickupCommandHandler: user_id=%d intentando recoger item", user_id)

        # Obtener posición del jugador
        position = await self.player_repo.get_position(user_id)
        if not position:
            logger.error("No se pudo obtener posición del jugador %d", user_id)
            return CommandResult.error("No se pudo obtener la posición del jugador")

        map_id = position["map"]
        x = position["x"]
        y = position["y"]

        # Buscar items en ese tile
        items = self.map_manager.get_ground_items(map_id, x, y)

        if not items:
            await self.message_sender.send_console_msg("No hay nada aquí.")
            logger.info("Jugador %d intentó recoger pero no hay items en (%d,%d)", user_id, x, y)
            return CommandResult.error("No hay nada aquí")

        # Recoger primer item
        item = items[0]
        item_id = item.get("item_id")
        quantity = item.get("quantity", 1)

        # Validar tipos
        if not isinstance(quantity, int):
            quantity = 1
        if not isinstance(item_id, int) and item_id is not None:
            logger.warning("item_id inválido: %s", item_id)
            return CommandResult.error("Item inválido")

        # El loot siempre es público - cualquiera puede recogerlo
        # (owner_id se mantiene para compatibilidad futura, pero no se verifica)

        # Manejar oro especialmente
        if item_id == GOLD_ITEM_ID:
            result = await self._pickup_gold(user_id, quantity, map_id, x, y)
        else:
            result = await self._pickup_item(user_id, item_id, quantity, map_id, x, y)

        return result

    async def _pickup_gold(
        self, user_id: int, gold: int, map_id: int, x: int, y: int
    ) -> CommandResult:
        """Recoge oro del suelo.

        Args:
            user_id: ID del jugador.
            gold: Cantidad de oro.
            map_id: ID del mapa.
            x: Posición X.
            y: Posición Y.

        Returns:
            Resultado de la ejecución.
        """
        # Obtener oro actual
        current_gold = await self.player_repo.get_gold(user_id)
        new_gold = current_gold + gold

        # Actualizar oro
        await self.player_repo.update_gold(user_id, new_gold)

        # Enviar UPDATE_USER_STATS al cliente para actualizar GUI
        # TODO: Optimizar para enviar solo el oro en lugar de todos los stats
        stats = await self.player_repo.get_player_stats(user_id)
        if stats:
            await self.message_sender.send_update_user_stats(
                max_hp=stats.max_hp,
                min_hp=stats.min_hp,
                max_mana=stats.max_mana,
                min_mana=stats.min_mana,
                max_sta=stats.max_sta,
                min_sta=stats.min_sta,
                gold=new_gold,
                level=stats.level,
                elu=stats.elu,
                experience=stats.experience,
            )

        # Remover del suelo
        self.map_manager.remove_ground_item(map_id, x, y, item_index=0)

        # Broadcast OBJECT_DELETE
        if self.broadcast_service:
            await self.broadcast_service.broadcast_object_delete(map_id, x, y)

        # Notificar al jugador
        await self.message_sender.send_console_msg(f"Recogiste {gold} monedas de oro.")
        logger.info("Jugador %d recogió %d de oro en (%d,%d)", user_id, gold, x, y)

        return CommandResult.ok(data={"item_id": GOLD_ITEM_ID, "quantity": gold, "type": "gold"})

    async def _pickup_item(
        self, user_id: int, item_id: int | None, quantity: int, map_id: int, x: int, y: int
    ) -> CommandResult:
        """Recoge un item del suelo.

        Args:
            user_id: ID del jugador.
            item_id: ID del item.
            quantity: Cantidad.
            map_id: ID del mapa.
            x: Posición X.
            y: Posición Y.

        Returns:
            Resultado de la ejecución.
        """
        if not self.inventory_repo or not item_id or not self.item_catalog:
            return CommandResult.error("Servicios no disponibles para recoger item")

        # Obtener datos del item del catálogo
        item_data = self.item_catalog.get_item_data(item_id)
        if not item_data:
            logger.warning("Item %d no encontrado en el catálogo", item_id)
            return CommandResult.error(f"Item {item_id} no encontrado en el catálogo")

        # Agregar item al inventario
        modified_slots = await self.inventory_repo.add_item(user_id, item_id, quantity)

        if not modified_slots:
            await self.message_sender.send_console_msg("Tu inventario está lleno.")
            return CommandResult.error("Inventario lleno")

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

        return CommandResult.ok(
            data={"item_id": item_id, "quantity": quantity, "type": "item", "slots": modified_slots}
        )
