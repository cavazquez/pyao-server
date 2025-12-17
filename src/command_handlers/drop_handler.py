"""Handler para comando de soltar item."""

import logging
from typing import TYPE_CHECKING

from src.command_handlers.drop_gold_handler import DropGoldHandler
from src.command_handlers.drop_item_handler import DropItemHandler
from src.commands.base import Command, CommandHandler, CommandResult
from src.commands.drop_command import DropCommand

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

        # Inicializar handlers especializados
        self.gold_handler = DropGoldHandler(
            player_repo=player_repo,
            map_manager=map_manager,
            broadcast_service=broadcast_service,
            message_sender=message_sender,
        )

        self.item_handler = DropItemHandler(
            player_repo=player_repo,
            inventory_repo=inventory_repo,
            map_manager=map_manager,
            broadcast_service=broadcast_service,
            message_sender=message_sender,
            item_catalog=item_catalog,
        )

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
            success, error_msg, data = await self.gold_handler.drop_gold(user_id, quantity)
            if success:
                return CommandResult.ok(data=data)
            return CommandResult.error(error_msg or "Error al tirar oro")

        success, error_msg, data = await self.item_handler.drop_item(user_id, slot, quantity)
        if success:
            return CommandResult.ok(data=data)
        return CommandResult.error(error_msg or "Error al tirar item")
