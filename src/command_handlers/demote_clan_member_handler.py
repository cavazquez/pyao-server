"""Handler para comando de degradar miembro de clan."""

import logging
from typing import TYPE_CHECKING

from src.commands.base import Command, CommandHandler, CommandResult
from src.commands.demote_clan_member_command import DemoteClanMemberCommand

if TYPE_CHECKING:
    from src.services.clan_service import ClanService

logger = logging.getLogger(__name__)


class DemoteClanMemberCommandHandler(CommandHandler):
    """Handler para comando de degradar miembro de clan."""

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
        """Maneja el comando de degradar miembro de clan.

        Args:
            command: Comando de degradar miembro.

        Returns:
            CommandResult con el resultado de la operación.
            Si es exitoso, contiene message en data.
            Si falla, contiene error_message.
        """
        if not isinstance(command, DemoteClanMemberCommand):
            return CommandResult.error("Comando inválido")

        try:
            success, message = await self.clan_service.demote_member(
                demoter_id=self.user_id,
                target_username=command.target_username,
            )

            if success:
                logger.info(
                    "Usuario %s degradó a '%s' en su clan",
                    self.user_id,
                    command.target_username,
                )
                return CommandResult.ok(data={"message": message})
            return CommandResult.error(message)

        except Exception:
            logger.exception("Error al degradar miembro de clan")
            return CommandResult.error("Error interno al degradar miembro")
