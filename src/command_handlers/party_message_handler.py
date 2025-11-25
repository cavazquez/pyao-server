"""Handler para comando de enviar mensaje a party."""

import logging
from typing import TYPE_CHECKING

from src.commands.base import Command, CommandHandler, CommandResult
from src.commands.party_message_command import PartyMessageCommand

if TYPE_CHECKING:
    from src.messaging.message_sender import MessageSender
    from src.services.party_service import PartyService

logger = logging.getLogger(__name__)


class PartyMessageCommandHandler(CommandHandler):
    """Handler para comando de enviar mensaje a party (solo lógica de negocio)."""

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
        """Ejecuta el comando de enviar mensaje a party (solo lógica de negocio).

        Args:
            command: Comando de enviar mensaje.

        Returns:
            Resultado de la ejecución.
        """
        if not isinstance(command, PartyMessageCommand):
            return CommandResult.error("Comando inválido: se esperaba PartyMessageCommand")

        user_id = command.user_id
        message = command.message

        logger.info("PartyMessageCommandHandler: user_id=%d envía mensaje a party", user_id)

        try:
            # Send party message
            result = await self.party_service.send_party_message(user_id, message)

            # If there's an error message, send it to sender
            if result:
                await self.message_sender.send_console_msg(
                    result,
                    font_color=7,  # FONTTYPE_PARTY
                )

            logger.info("User %s sent party message: %s...", user_id, message[:50])

            return CommandResult.ok(data={"message": message, "error": result or None})

        except Exception as e:
            logger.exception("Error sending party message for user %s", user_id)
            await self.message_sender.send_console_msg(
                "Error al enviar mensaje a la party. Intenta nuevamente.",
                font_color=1,  # FONTTYPE_FIGHT (red for errors)
            )
            return CommandResult.error(f"Error al enviar mensaje a la party: {e!s}")
