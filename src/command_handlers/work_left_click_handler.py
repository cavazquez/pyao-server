"""Trabajo con objetivo: validación y commit común de recurso y entrenamiento."""

from typing import TYPE_CHECKING

from src.commands.base import Command, CommandHandler, CommandResult
from src.commands.work_left_click_command import WorkLeftClickCommand
from src.services.action_cadence import ActionCadence
from src.services.gathering import gather
from src.services.inventory_notifications import notify_inventory
from src.services.player_progression import publish_progress

if TYPE_CHECKING:
    from src.messaging.message_sender import MessageSender
    from src.repositories.inventory_repository import InventoryRepository
    from src.repositories.player_repository import PlayerRepository
    from src.services.map.map_resources_service import MapResourcesService
    from src.services.skill_action_service import SkillActionService


class WorkLeftClickCommandHandler(CommandHandler):
    """Toda recolección pasa por el mismo plan atómico y presupuesto de cadencia."""

    def __init__(
        self,
        player_repo: PlayerRepository,
        inventory_repo: InventoryRepository,
        map_resources: MapResourcesService | None,
        message_sender: MessageSender,
        action_cadence: ActionCadence | None = None,
        skill_actions: SkillActionService | None = None,
    ) -> None:
        """Recibe repositorios y cadencia compartidos; no almacena sesiones ajenas."""
        self.skill_actions = skill_actions
        self.player_repo = player_repo
        self.inventory_repo = inventory_repo
        self.map_resources = map_resources
        self.message_sender = message_sender
        self.action_cadence = action_cadence or ActionCadence()

    async def handle(self, command: Command) -> CommandResult:
        """Ejecuta únicamente un intento válido de recolección.

        Returns:
            Resultado confirmado o motivo de rechazo sin otorgar XP.
        """
        if not isinstance(command, WorkLeftClickCommand) or self.map_resources is None:
            return CommandResult.error("Servicio de trabajo no disponible")
        if self.skill_actions is not None:
            result = await self.skill_actions.execute(
                command.user_id,
                "work",
                {"skill": command.skill_type, "x": command.target_x, "y": command.target_y},
                self.message_sender,
            )
            return (
                CommandResult.ok(result)
                if result["applied"]
                else CommandResult.error(str(result.get("message", "Trabajo rechazado")))
            )
        if not self.action_cadence.claim(command.user_id, "work"):
            return CommandResult.error("Acción demasiado frecuente")
        try:
            result = await gather(
                self.player_repo,
                self.inventory_repo,
                self.map_resources,
                command.user_id,
                command.skill_type,
                command.map_id,
                command.target_x,
                command.target_y,
            )
            await self.message_sender.send_console_msg(str(result["message"]))
            if not result["applied"]:
                return CommandResult.error(str(result["message"]))
            if result.get("quantity"):
                await notify_inventory(self.message_sender, self.inventory_repo, command.user_id)
            await publish_progress(self.player_repo, command.user_id, self.message_sender)
            return CommandResult.ok(result)
        finally:
            self.action_cadence.release(command.user_id, "work")
