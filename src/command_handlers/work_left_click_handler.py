"""Handler para comando de trabajo con click (pesca, tala, minería)."""

import logging
from typing import TYPE_CHECKING

from src.command_handlers.work_left_click_execution_handler import (
    WorkLeftClickExecutionHandler,
)
from src.command_handlers.work_left_click_ui_handler import WorkLeftClickUIHandler
from src.command_handlers.work_left_click_validation_handler import (
    WorkLeftClickValidationHandler,
)
from src.commands.base import Command, CommandHandler, CommandResult
from src.commands.work_left_click_command import WorkLeftClickCommand

if TYPE_CHECKING:
    from src.messaging.message_sender import MessageSender
    from src.repositories.inventory_repository import InventoryRepository
    from src.repositories.player_repository import PlayerRepository
    from src.services.map.map_resources_service import MapResourcesService

logger = logging.getLogger(__name__)


class WorkLeftClickCommandHandler(CommandHandler):
    """Handler para comando de trabajo con click (solo lógica de negocio)."""

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

        # Inicializar handlers especializados
        self.validation_handler = WorkLeftClickValidationHandler(
            player_repo=player_repo,
            inventory_repo=inventory_repo,
            message_sender=message_sender,
        )

        self.execution_handler = WorkLeftClickExecutionHandler(
            player_repo=player_repo,
            inventory_repo=inventory_repo,
            map_resources=map_resources,
            message_sender=message_sender,
        )

        self.ui_handler = WorkLeftClickUIHandler(
            inventory_repo=inventory_repo,
            message_sender=message_sender,
        )

    async def handle(self, command: Command) -> CommandResult:  # noqa: PLR0914
        """Ejecuta el comando de trabajo con click (solo lógica de negocio).

        Args:
            command: Comando de trabajo con click.

        Returns:
            Resultado de la ejecución.
        """
        if not isinstance(command, WorkLeftClickCommand):
            return CommandResult.error("Comando inválido: se esperaba WorkLeftClickCommand")

        user_id = command.user_id
        map_id = command.map_id
        target_x = command.target_x
        target_y = command.target_y
        skill_type = command.skill_type

        logger.info(
            "WorkLeftClickCommandHandler: user_id=%d intenta trabajar en mapa=%d, "
            "posición=(%d, %d), skill=%d",
            user_id,
            map_id,
            target_x,
            target_y,
            skill_type,
        )

        try:
            # Verificar distancia
            if not await self.validation_handler.check_distance(user_id, target_x, target_y):
                return CommandResult.error("Debes estar a un tile de distancia para trabajar")

            # Verificar herramientas
            has_hacha, has_pico, has_cana = await self.validation_handler.check_tools(user_id)

            # Verificar si no tiene herramientas
            if await self.validation_handler.check_no_tools(has_hacha, has_pico, has_cana):
                return CommandResult.error(
                    "Necesitas una herramienta (hacha, pico o caña de pescar)"
                )

            # Intentar trabajar en la posición clickeada
            work_result = await self.execution_handler.try_work_at_position(
                user_id, map_id, target_x, target_y, skill_type, has_hacha, has_pico, has_cana
            )

            if work_result:
                (
                    resource_name,
                    item_id,
                    quantity,
                    slot,
                    skill_name,
                    exp_gained,
                    leveled_up,
                ) = work_result

                # Enviar mensajes al cliente
                await self.ui_handler.send_work_messages(
                    resource_name, quantity, skill_name, exp_gained, leveled_up
                )

                # Actualizar UI del inventario
                await self.ui_handler.update_inventory_ui(user_id, item_id, slot)

                logger.info(
                    "Usuario %d obtuvo %d %s (item_id=%d, slot=%d) + %d exp %s",
                    user_id,
                    quantity,
                    resource_name,
                    item_id,
                    slot,
                    exp_gained,
                    skill_name,
                )

                return CommandResult.ok(
                    data={
                        "resource_name": resource_name,
                        "item_id": item_id,
                        "quantity": quantity,
                        "slot": slot,
                        "skill_name": skill_name,
                        "exp_gained": exp_gained,
                        "leveled_up": leveled_up,
                    }
                )

            await self.message_sender.console.send_console_msg(
                "No hay nada para trabajar en esa posición"
            )
            return CommandResult.error("No hay nada para trabajar en esa posición")

        except Exception as e:
            logger.exception("Error al trabajar con click")
            return CommandResult.error(f"Error al trabajar: {e!s}")
