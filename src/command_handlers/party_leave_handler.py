"""Handler para comando de abandonar party."""

import logging
from typing import TYPE_CHECKING

from src.commands.base import Command, CommandHandler, CommandResult
from src.commands.party_leave_command import PartyLeaveCommand

if TYPE_CHECKING:
    from src.messaging.message_sender import MessageSender
    from src.services.party_service import PartyService

logger = logging.getLogger(__name__)


class PartyLeaveCommandHandler(CommandHandler):
    """Handler para comando de abandonar party (solo lógica de negocio)."""

    def __init__(
        self,
        party_service: PartyService,
        message_sender: MessageSender,
    ) -> None:
        """Inicializa el handler.

        Args:
            party_service: Servicio de party.
            message_sender: Enviador de mensajes.
        """
        self.party_service = party_service
        self.message_sender = message_sender

    async def handle(self, command: Command) -> CommandResult:
        """Ejecuta el comando de abandonar party (solo lógica de negocio).

        Args:
            command: Comando de abandonar party.

        Returns:
            Resultado de la ejecución.
        """
        if not isinstance(command, PartyLeaveCommand):
            return CommandResult.error("Comando inválido: se esperaba PartyLeaveCommand")

        user_id = command.user_id

        logger.info("PartyLeaveCommandHandler: user_id=%d intenta abandonar party", user_id)

        try:
            # Leave party
            message = await self.party_service.leave_party(user_id)

            # Send result message
            await self.message_sender.send_console_msg(message, font_color=7)

            logger.info("User %s left party", user_id)

            return CommandResult.ok(data={"message": message})

        except Exception as e:
            logger.exception("Error leaving party")
            await self.message_sender.send_console_msg(
                "Error al abandonar la party. Intenta nuevamente.", font_color=1
            )
            return CommandResult.error(f"Error al abandonar la party: {e!s}")
