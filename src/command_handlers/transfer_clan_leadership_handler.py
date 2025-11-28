"""Handler para comando de transferir liderazgo de clan."""

import logging
from typing import TYPE_CHECKING

from src.commands.base import Command, CommandHandler, CommandResult
from src.commands.transfer_clan_leadership_command import TransferClanLeadershipCommand

if TYPE_CHECKING:
    from src.services.clan_service import ClanService

logger = logging.getLogger(__name__)


class TransferClanLeadershipCommandHandler(CommandHandler):
    """Handler para comando de transferir liderazgo de clan."""

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
        """Maneja el comando de transferir liderazgo de clan.

        Args:
            command: Comando de transferir liderazgo.

        Returns:
            CommandResult con el resultado de la operación.
            Si es exitoso, contiene message en data.
            Si falla, contiene error_message.
        """
        if not isinstance(command, TransferClanLeadershipCommand):
            return CommandResult.error("Comando inválido")

        try:
            success, message = await self.clan_service.transfer_leadership(
                leader_id=self.user_id,
                new_leader_username=command.new_leader_username,
            )

            if success:
                logger.info(
                    "Usuario %s transfirió el liderazgo a '%s' en su clan",
                    self.user_id,
                    command.new_leader_username,
                )
                return CommandResult.ok(data={"message": message})
            return CommandResult.error(message)

        except Exception:
            logger.exception("Error al transferir liderazgo de clan")
            return CommandResult.error("Error interno al transferir liderazgo")
