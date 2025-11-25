"""Handler para comando de abandonar clan."""

import logging
from typing import TYPE_CHECKING

from src.commands.base import Command, CommandHandler, CommandResult
from src.commands.leave_clan_command import LeaveClanCommand

if TYPE_CHECKING:
    from src.services.clan_service import ClanService

logger = logging.getLogger(__name__)


class LeaveClanCommandHandler(CommandHandler):
    """Handler para comando de abandonar clan."""

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
        """Maneja el comando de abandonar clan.

        Args:
            command: Comando de abandonar clan.

        Returns:
            CommandResult con el resultado de la operación.
        """
        if not isinstance(command, LeaveClanCommand):
            return CommandResult.error("Comando inválido")

        try:
            success, message = await self.clan_service.leave_clan(user_id=self.user_id)

            if success:
                logger.info("Usuario %s abandonó su clan", self.user_id)
                return CommandResult.ok(data={"message": message})
            return CommandResult.error(message)

        except Exception:
            logger.exception("Error al abandonar clan")
            return CommandResult.error("Error interno al abandonar clan")
