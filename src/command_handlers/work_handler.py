"""Trabajo frontal y solicitud de objetivo con el mismo motor de recolección."""

from typing import TYPE_CHECKING

from src.command_handlers.work_left_click_handler import WorkLeftClickCommandHandler
from src.commands.base import Command, CommandHandler, CommandResult
from src.commands.work_command import WorkCommand
from src.commands.work_left_click_command import WorkLeftClickCommand
from src.services.action_cadence import ActionCadence
from src.services.gathering import GATHERING

HIDE_SKILL = 7


if TYPE_CHECKING:
    from src.messaging.message_sender import MessageSender
    from src.repositories.inventory_repository import InventoryRepository
    from src.repositories.player_repository import PlayerRepository
    from src.services.map.map_resources_service import MapResourcesService
    from src.services.skill_action_service import SkillActionService


class WorkCommandHandler(CommandHandler):
    """Reutiliza la acción con objetivo y mantiene el trabajo de frente."""

    def __init__(
        self,
        player_repo: PlayerRepository,
        inventory_repo: InventoryRepository,
        map_resources: MapResourcesService | None,
        message_sender: MessageSender,
        action_cadence: ActionCadence | None = None,
        skill_actions: SkillActionService | None = None,
    ) -> None:
        """Recibe las dependencias del jugador autenticado y su emisor."""
        self.skill_actions = skill_actions
        self.player_repo = player_repo
        self.inventory_repo = inventory_repo
        self.map_resources = map_resources
        self.message_sender = message_sender
        self.action_cadence = action_cadence or ActionCadence()

    async def handle(self, command: Command) -> CommandResult:
        """Recolecta delante del personaje o solicita una casilla para la habilidad.

        Returns:
            Resultado de la acción o rechazo autoritativo.
        """
        if not isinstance(command, WorkCommand) or self.map_resources is None:
            return CommandResult.error("Servicio de trabajo no disponible")
        if self.skill_actions is not None:
            if command.skill_type == HIDE_SKILL:
                result = await self.skill_actions.execute(
                    command.user_id, "hide", {}, self.message_sender
                )
                return (
                    CommandResult.ok(result)
                    if result["applied"]
                    else CommandResult.error(str(result.get("message", "Acción rechazada")))
                )
            if command.skill_type in {2, 8, 17, 18}:
                await self.message_sender.send_work_request_target(command.skill_type)
                return CommandResult.ok({"target_requested": command.skill_type})
        queries = {
            9: self.map_resources.has_tree,
            13: self.map_resources.has_mine,
            12: self.map_resources.has_water,
        }
        for skill in GATHERING:
            if command.skill_type in {0, skill} and queries[skill](
                command.map_id, command.target_x, command.target_y
            ):
                handler = WorkLeftClickCommandHandler(
                    self.player_repo,
                    self.inventory_repo,
                    self.map_resources,
                    self.message_sender,
                    self.action_cadence,
                    self.skill_actions,
                )
                return await handler.handle(
                    WorkLeftClickCommand(
                        user_id=command.user_id,
                        map_id=command.map_id,
                        target_x=command.target_x,
                        target_y=command.target_y,
                        skill_type=skill,
                    )
                )
        if command.skill_type in GATHERING:
            await self.message_sender.send_work_request_target(command.skill_type)
            return CommandResult.ok({"target_requested": command.skill_type})
        return CommandResult.error("No hay un recurso apropiado en esa dirección")
