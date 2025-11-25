"""Handler para comando de invitar a un clan."""

import logging
from typing import TYPE_CHECKING

from src.commands.base import Command, CommandHandler, CommandResult
from src.commands.invite_clan_command import InviteClanCommand

if TYPE_CHECKING:
    from src.services.clan_service import ClanService

logger = logging.getLogger(__name__)


class InviteClanCommandHandler(CommandHandler):
    """Handler para comando de invitar a un clan."""

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
        """Maneja el comando de invitar a un clan.

        Args:
            command: Comando de invitación a clan.

        Returns:
            CommandResult con el resultado de la operación.
            Si es exitoso, contiene message en data.
            Si falla, contiene error_message.
        """
        if not isinstance(command, InviteClanCommand):
            return CommandResult.error("Comando inválido")

        try:
            message = await self.clan_service.invite_to_clan(
                inviter_id=self.user_id,
                target_username=command.target_username,
            )

            logger.info(
                "Usuario %s invitó a '%s' a unirse a un clan",
                self.user_id,
                command.target_username,
            )
            return CommandResult.ok(data={"message": message})

        except Exception:
            logger.exception("Error al invitar a clan")
            return CommandResult.error("Error interno al invitar a clan")
