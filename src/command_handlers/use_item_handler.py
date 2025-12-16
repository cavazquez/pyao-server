"""Handler para comando de usar item."""

import logging
from typing import TYPE_CHECKING

from src.command_handlers.use_item_consumable_handler import UseItemConsumableHandler
from src.command_handlers.use_item_special_handler import UseItemSpecialHandler
from src.commands.base import Command, CommandHandler, CommandResult
from src.commands.use_item_command import UseItemCommand
from src.models.item_constants import BOAT_ITEM_ID
from src.models.item_types import ObjType
from src.repositories.inventory_repository import InventoryRepository

if TYPE_CHECKING:
    from src.game.map_manager import MapManager
    from src.messaging.message_sender import MessageSender
    from src.models.item_catalog import ItemCatalog
    from src.repositories.account_repository import AccountRepository
    from src.repositories.player_repository import PlayerRepository
    from src.services.map.map_resources_service import MapResourcesService
    from src.services.multiplayer_broadcast_service import (
        MultiplayerBroadcastService,
    )

logger = logging.getLogger(__name__)

WORK_TOOL_SKILLS: dict[int, int] = {
    561: 9,  # Hacha de Leñador → Skill Talar
    562: 13,  # Piquete de Minero → Skill Minería
    563: 12,  # Caña de pescar → Skill Pesca
}


class UseItemCommandHandler(CommandHandler):
    """Handler para comando de usar item (solo lógica de negocio).

    Este handler delega a handlers especializados según el tipo de item:
    - UseItemConsumableHandler: Para pociones y comida
    - UseItemSpecialHandler: Para barca y herramientas de trabajo
    """

    def __init__(
        self,
        player_repo: PlayerRepository,
        map_resources: MapResourcesService | None,
        account_repo: AccountRepository | None,
        message_sender: MessageSender,
        item_catalog: ItemCatalog | None = None,
        broadcast_service: MultiplayerBroadcastService | None = None,
        map_manager: MapManager | None = None,
    ) -> None:
        """Inicializa el handler.

        Args:
            player_repo: Repositorio de jugadores.
            map_resources: Servicio de recursos de mapa.
            account_repo: Repositorio de cuentas.
            message_sender: Enviador de mensajes.
            item_catalog: Catálogo de items (para datos completos de pociones).
            broadcast_service: Servicio de broadcast multijugador (para invisibilidad).
            map_manager: Gestor de mapas (para obtener message senders).
        """
        self.player_repo = player_repo
        self.map_resources = map_resources
        self.account_repo = account_repo
        self.message_sender = message_sender
        self.item_catalog = item_catalog
        self.broadcast_service = broadcast_service
        self.map_manager = map_manager

        # Inicializar handlers especializados
        self.consumable_handler = UseItemConsumableHandler(
            player_repo=player_repo,
            message_sender=message_sender,
            item_catalog=item_catalog,
            broadcast_service=broadcast_service,
            map_manager=map_manager,
            account_repo=account_repo,
        )

        self.special_handler = UseItemSpecialHandler(
            player_repo=player_repo,
            map_resources=map_resources,
            account_repo=account_repo,
            message_sender=message_sender,
        )

    async def handle(self, command: Command) -> CommandResult:
        """Ejecuta el comando de usar item (solo lógica de negocio).

        Args:
            command: Comando de usar item.

        Returns:
            Resultado de la ejecución.
        """
        if not isinstance(command, UseItemCommand):
            return CommandResult.error("Comando inválido: se esperaba UseItemCommand")

        user_id = command.user_id
        slot = command.slot
        username = command.username

        logger.debug(
            "UseItemCommandHandler: Procesando uso de item user_id=%d slot=%d", user_id, slot
        )

        # Validar dependencias
        if not self.player_repo:
            logger.error("PlayerRepository no está disponible para usar item")
            return CommandResult.error("Error interno: repositorio no disponible")

        inventory_repo = InventoryRepository(self.player_repo.redis)
        slot_data = await inventory_repo.get_slot(user_id, slot)

        if not slot_data:
            logger.warning("Slot %d vacío", slot)
            return CommandResult.error("El slot está vacío")

        item_id, quantity = slot_data

        # Herramientas de trabajo: delegar a handler especializado
        if item_id in WORK_TOOL_SKILLS:
            return await self.special_handler.handle_work_tool(user_id, item_id, slot)

        # Barca: delegar a handler especializado
        if item_id == BOAT_ITEM_ID:
            return await self.special_handler.handle_boat(user_id, slot, username)

        # Caso especial para manzanas (ID 1): delegar a handler de consumibles
        if item_id == 1:
            return await self.consumable_handler.handle_apple(
                user_id, item_id, quantity, slot, inventory_repo
            )

        # Detectar si es una poción: delegar a handler de consumibles
        if self.item_catalog:
            item_data = self.item_catalog.get_item_data(item_id)
            if item_data:
                obj_type = item_data.get("ObjType")
                if isinstance(obj_type, int) and obj_type == ObjType.POCIONES:
                    potion_type = item_data.get("TipoPocion")
                    if isinstance(potion_type, int):
                        return await self.consumable_handler.handle_potion(
                            user_id,
                            item_id,
                            quantity,
                            slot,
                            inventory_repo,
                            item_data,
                            potion_type,
                        )

        # Si llegamos aquí, el ítem no tiene un comportamiento definido
        logger.info("El ítem %d no tiene un comportamiento de uso definido", item_id)
        return CommandResult.ok(data={"item_id": item_id, "handled": False})
