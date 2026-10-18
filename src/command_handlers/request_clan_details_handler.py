"""Handler para comando de solicitar detalles del clan."""

import logging
from typing import TYPE_CHECKING

from src.commands.base import Command, CommandHandler, CommandResult
from src.commands.request_clan_details_command import RequestClanDetailsCommand
from src.models.clan import Clan

if TYPE_CHECKING:
    from src.messaging.message_sender import MessageSender
    from src.services.clan_service import ClanService

logger = logging.getLogger(__name__)


class RequestClanDetailsCommandHandler(CommandHandler):
    """Handler para comando de solicitar detalles del clan."""

    def __init__(
        self,
        clan_service: ClanService,
        message_sender: MessageSender,
        user_id: int,
    ) -> None:
        """Inicializa el handler.

        Args:
            clan_service: Servicio de clanes.
            message_sender: Enviador de mensajes.
            user_id: ID del usuario que solicita los detalles.
        """
        self.clan_service = clan_service
        self.message_sender = message_sender
        self.user_id = user_id

    async def handle(self, command: Command) -> CommandResult:
        """Maneja el comando de solicitar detalles del clan.

        Args:
            command: Comando de solicitar detalles del clan.

        Returns:
            CommandResult con el resultado de la operación.
        """
        if not isinstance(command, RequestClanDetailsCommand):
            return CommandResult.error("Comando inválido")

        try:
            # Obtener el clan del usuario
            clan = await self.clan_service.clan_repo.get_user_clan(self.user_id)
            if not clan or clan.get_member(self.user_id) is None:
                # Estado vacío estándar: permite confirmar un abandono y limpiar la UI.
                await self.message_sender.send_clan_details(Clan(clan_id=0, name="", created_at=0))
                return CommandResult.error("No perteneces a ningún clan")
            await self.message_sender.send_clan_details(clan)

            logger.info("Detalles del clan '%s' enviados a user_id %s", clan.name, self.user_id)
            return CommandResult.ok()

        except Exception:
            logger.exception("Error al obtener detalles del clan")
            return CommandResult.error("Error interno al obtener detalles del clan")
