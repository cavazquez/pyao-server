"""Handler para comando de recoger item."""

import logging
from typing import TYPE_CHECKING, Any, cast

from src.command_handlers.pickup_gold_handler import PickupGoldHandler
from src.command_handlers.pickup_item_handler import PickupItemHandler
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

        # Inicializar handlers especializados
        self.gold_handler = PickupGoldHandler(
            player_repo=player_repo,
            map_manager=map_manager,
            broadcast_service=broadcast_service,
            message_sender=message_sender,
        )

        self.item_handler = PickupItemHandler(
            player_repo=player_repo,
            inventory_repo=inventory_repo,
            map_manager=map_manager,
            broadcast_service=broadcast_service,
            item_catalog=item_catalog,
            message_sender=message_sender,
        )

    async def handle(self, command: Command) -> CommandResult:
        """Ejecuta el comando de recoger item (solo lógica de negocio).

        La implementación sigue el patrón *claim-first* para evitar
        duplicación de items por race condition entre múltiples pickups
        simultáneos sobre el mismo tile:

        1. Leemos la posición del jugador (requiere un await en Redis).
        2. *Reclamamos* el item del suelo de forma síncrona: ``remove_ground_item``
           modifica un ``dict`` en memoria sin awaits, así que una única
           coroutine puede ejecutar el pop antes de que otra llegue al mismo
           punto.
        3. Ejecutamos la parte con awaits (escritura en Redis, broadcast).
        4. Si la escritura falla (inventario lleno, tope de oro, etc.),
           *restauramos* el item al tile original para no perder estado.

        Args:
            command: Comando de recoger item.

        Returns:
            Resultado de la ejecución.
        """
        if not isinstance(command, PickupCommand):
            return CommandResult.error("Comando inválido: se esperaba PickupCommand")

        user_id = command.user_id

        logger.info("PickupCommandHandler: user_id=%d intentando recoger item", user_id)

        position = await self.player_repo.get_position(user_id)
        if not position:
            logger.error("No se pudo obtener posición del jugador %d", user_id)
            return CommandResult.error("No se pudo obtener la posición del jugador")

        map_id = position["map"]
        x = position["x"]
        y = position["y"]

        # Paso crítico: claim sincrónico. Entre este remove_ground_item y el
        # add_item del inventario no hay ningún await, así que otra coroutine
        # que corra en paralelo verá el tile sin items y saldrá por el camino
        # de "No hay nada aquí".
        claimed = self.map_manager.remove_ground_item(map_id, x, y, item_index=0)
        if claimed is None:
            await self.message_sender.send_console_msg("No hay nada aquí.")
            logger.info("Jugador %d intentó recoger pero no hay items en (%d,%d)", user_id, x, y)
            return CommandResult.error("No hay nada aquí")

        item_id = claimed.get("item_id")
        quantity = claimed.get("quantity", 1)

        if not isinstance(quantity, int):
            quantity = 1
        if not isinstance(item_id, int) and item_id is not None:
            logger.warning("item_id inválido: %s", item_id)
            # Restaurar al suelo: el estado del tile no puede corromperse
            # por datos malformados en Redis.
            self.map_manager.add_ground_item(map_id, x, y, claimed)
            return CommandResult.error("Item inválido")

        # El loot siempre es público - cualquiera puede recogerlo
        # (owner_id se mantiene para compatibilidad futura, pero no se verifica)

        if item_id == GOLD_ITEM_ID:
            success, error_msg, gold_data = await self.gold_handler.pickup_claimed_gold(
                user_id, quantity, map_id, x, y
            )
            if success and gold_data:
                return CommandResult.ok(data=cast("Any", gold_data))
            # Gold handler rechazó: restaurar
            self.map_manager.add_ground_item(map_id, x, y, claimed)
            return CommandResult.error(error_msg or "Error al recoger oro")

        success, error_msg, item_data = await self.item_handler.pickup_claimed_item(
            user_id, item_id, quantity, map_id, x, y
        )
        if success and item_data:
            return CommandResult.ok(data=cast("Any", item_data))
        # Item handler rechazó (inventario lleno): restaurar
        self.map_manager.add_ground_item(map_id, x, y, claimed)
        return CommandResult.error(error_msg or "Error al recoger item")
