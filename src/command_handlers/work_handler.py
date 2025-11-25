"""Handler para comando de trabajo (talar, minar, pescar)."""

import logging
from typing import TYPE_CHECKING

from src.commands.base import Command, CommandHandler, CommandResult
from src.commands.work_command import WorkCommand
from src.constants.items import ResourceItemID, ToolID

if TYPE_CHECKING:
    from src.messaging.message_sender import MessageSender
    from src.repositories.inventory_repository import InventoryRepository
    from src.repositories.player_repository import PlayerRepository
    from src.services.map.map_resources_service import MapResourcesService

logger = logging.getLogger(__name__)


class WorkCommandHandler(CommandHandler):
    """Handler para comando de trabajo (solo lógica de negocio)."""

    def __init__(
        self,
        player_repo: PlayerRepository,
        inventory_repo: InventoryRepository,
        map_resources: MapResourcesService | None,
        message_sender: MessageSender,
    ) -> None:
        """Inicializa el handler.

        Args:
            player_repo: Repositorio de jugadores.
            inventory_repo: Repositorio de inventario.
            map_resources: Servicio de recursos del mapa.
            message_sender: Enviador de mensajes.
        """
        self.player_repo = player_repo
        self.inventory_repo = inventory_repo
        self.map_resources = map_resources
        self.message_sender = message_sender

    async def handle(self, command: Command) -> CommandResult:
        """Ejecuta el comando de trabajo (solo lógica de negocio).

        Args:
            command: Comando de trabajo.

        Returns:
            Resultado de la ejecución.
        """
        if not isinstance(command, WorkCommand):
            return CommandResult.error("Comando inválido: se esperaba WorkCommand")

        user_id = command.user_id
        map_id = command.map_id
        target_x = command.target_x
        target_y = command.target_y

        logger.info(
            "WorkCommandHandler: user_id=%d intenta trabajar en mapa=%d, posición=(%d, %d)",
            user_id,
            map_id,
            target_x,
            target_y,
        )

        try:
            # Intentar trabajar en la posición objetivo
            work_result = await self._try_work_at_position(user_id, map_id, target_x, target_y)

            if work_result:
                resource_name, item_id, quantity = work_result
                await self.message_sender.console.send_console_msg(
                    f"Has obtenido {quantity} {resource_name}"
                )
                logger.info(
                    "Usuario %d obtuvo %d %s (item_id=%d)",
                    user_id,
                    quantity,
                    resource_name,
                    item_id,
                )
                return CommandResult.ok(
                    data={
                        "resource_name": resource_name,
                        "item_id": item_id,
                        "quantity": quantity,
                    }
                )
            await self.message_sender.console.send_console_msg(
                "No hay nada para trabajar en esa dirección"
            )
            return CommandResult.error("No hay nada para trabajar en esa dirección")

        except Exception as e:
            logger.exception("Error al trabajar")
            return CommandResult.error(f"Error al trabajar: {e!s}")

    async def _try_work_at_position(
        self, user_id: int, map_id: int, target_x: int, target_y: int
    ) -> tuple[str, int, int] | None:
        """Intenta trabajar en una posición específica.

        Args:
            user_id: ID del usuario.
            map_id: ID del mapa.
            target_x: Coordenada X objetivo.
            target_y: Coordenada Y objetivo.

        Returns:
            Tupla (nombre_recurso, item_id, cantidad) si se pudo trabajar, None si no.
        """
        # Verificar herramienta equipada o en inventario
        inventory = await self.inventory_repo.get_inventory_slots(user_id)

        has_hacha = any(slot.item_id == ToolID.HACHA_LENADOR for slot in inventory.values())
        has_pico = any(slot.item_id == ToolID.PIQUETE_MINERO for slot in inventory.values())
        has_cana = any(slot.item_id == ToolID.CANA_PESCAR for slot in inventory.values())

        # Verificar recursos usando MapResourcesService
        if self.map_resources:
            if has_hacha and self.map_resources.has_tree(map_id, target_x, target_y):
                await self.inventory_repo.add_item(user_id, item_id=ResourceItemID.LENA, quantity=5)
                return ("Leña", ResourceItemID.LENA, 5)

            if has_pico and self.map_resources.has_mine(map_id, target_x, target_y):
                await self.inventory_repo.add_item(
                    user_id, item_id=ResourceItemID.MINERAL_HIERRO, quantity=3
                )
                return ("Mineral de Hierro", ResourceItemID.MINERAL_HIERRO, 3)

            if has_cana and self.map_resources.has_water(map_id, target_x, target_y):
                await self.inventory_repo.add_item(
                    user_id, item_id=ResourceItemID.PESCADO, quantity=2
                )
                return ("Pescado", ResourceItemID.PESCADO, 2)

        # Si no tiene herramienta
        if not (has_hacha or has_pico or has_cana):
            await self.message_sender.console.send_console_msg(
                "Necesitas una herramienta (hacha, pico o caña de pescar)"
            )

        return None
