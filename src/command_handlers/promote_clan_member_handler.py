"""Handler para comando de promover miembro de clan."""

import logging
from typing import TYPE_CHECKING

from src.commands.base import Command, CommandHandler, CommandResult
from src.commands.promote_clan_member_command import PromoteClanMemberCommand

if TYPE_CHECKING:
    from src.services.clan_service import ClanService

logger = logging.getLogger(__name__)


class PromoteClanMemberCommandHandler(CommandHandler):
    """Handler para comando de promover miembro de clan."""

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
        """Maneja el comando de promover miembro de clan.

        Args:
            command: Comando de promover miembro.

        Returns:
            CommandResult con el resultado de la operación.
            Si es exitoso, contiene message en data.
            Si falla, contiene error_message.
        """
        if not isinstance(command, PromoteClanMemberCommand):
            return CommandResult.error("Comando inválido")

        try:
            success, message = await self.clan_service.promote_member(
                promoter_id=self.user_id,
                target_username=command.target_username,
            )

            if success:
                logger.info(
                    "Usuario %s promovió a '%s' en su clan",
                    self.user_id,
                    command.target_username,
                )
                return CommandResult.ok(data={"message": message})
            return CommandResult.error(message)

        except Exception:
            logger.exception("Error al promover miembro de clan")
            return CommandResult.error("Error interno al promover miembro")
