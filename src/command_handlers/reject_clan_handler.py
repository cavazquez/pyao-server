"""Handler para comando de rechazar invitación a clan."""

import logging
from typing import TYPE_CHECKING

from src.commands.base import Command, CommandHandler, CommandResult
from src.commands.reject_clan_command import RejectClanCommand

if TYPE_CHECKING:
    from src.services.clan_service import ClanService

logger = logging.getLogger(__name__)


class RejectClanCommandHandler(CommandHandler):
    """Handler para comando de rechazar invitación a clan."""

    def __init__(
        self,
        clan_service: ClanService,
        user_id: int,
    ) -> None:
        """Inicializa el handler.

        Args:
            clan_service: Servicio de clanes.
            user_id: ID del usuario que ejecuta el comando.
        """
        self.clan_service = clan_service
        self.user_id = user_id

    async def handle(self, command: Command) -> CommandResult:
        """Maneja el comando de rechazar invitación a clan.

        Args:
            command: Comando de rechazar invitación.

        Returns:
            CommandResult con el resultado de la operación.
            Si es exitoso, contiene message en data.
            Si falla, contiene error_message.
        """
        if not isinstance(command, RejectClanCommand):
            return CommandResult.error("Comando inválido")

        try:
            message = await self.clan_service.reject_invitation(user_id=self.user_id)

            logger.info("Usuario %s rechazó invitación a clan", self.user_id)
            return CommandResult.ok(data={"message": message})

        except Exception:
            logger.exception("Error al rechazar invitación a clan")
            return CommandResult.error("Error interno al rechazar invitación")
