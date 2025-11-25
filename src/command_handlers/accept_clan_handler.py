"""Handler para comando de aceptar invitación a clan."""

import logging
from typing import TYPE_CHECKING

from src.commands.accept_clan_command import AcceptClanCommand
from src.commands.base import Command, CommandHandler, CommandResult

if TYPE_CHECKING:
    from src.services.clan_service import ClanService

logger = logging.getLogger(__name__)


class AcceptClanCommandHandler(CommandHandler):
    """Handler para comando de aceptar invitación a clan."""

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
        """Maneja el comando de aceptar invitación a clan.

        Args:
            command: Comando de aceptar invitación.

        Returns:
            CommandResult con el resultado de la operación.
        """
        if not isinstance(command, AcceptClanCommand):
            return CommandResult.error("Comando inválido")

        try:
            clan, message = await self.clan_service.accept_invitation(user_id=self.user_id)

            if clan:
                logger.info("Usuario %s aceptó invitación al clan '%s'", self.user_id, clan.name)
                return CommandResult.ok(data={"clan_id": clan.clan_id, "clan_name": clan.name})
            return CommandResult.error(message)

        except Exception:
            logger.exception("Error al aceptar invitación a clan")
            return CommandResult.error("Error interno al aceptar invitación")
