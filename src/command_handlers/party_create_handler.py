"""Handler para comando de crear party."""

import logging
from typing import TYPE_CHECKING

from src.commands.base import Command, CommandHandler, CommandResult
from src.commands.party_create_command import PartyCreateCommand

if TYPE_CHECKING:
    from src.messaging.message_sender import MessageSender
    from src.services.party_service import PartyService

logger = logging.getLogger(__name__)


class PartyCreateCommandHandler(CommandHandler):
    """Handler para comando de crear party (solo lógica de negocio)."""

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
        """Ejecuta el comando de crear party (solo lógica de negocio).

        Args:
            command: Comando de crear party.

        Returns:
            Resultado de la ejecución.
        """
        if not isinstance(command, PartyCreateCommand):
            return CommandResult.error("Comando inválido: se esperaba PartyCreateCommand")

        user_id = command.user_id

        logger.info("PartyCreateCommandHandler: user_id=%d intenta crear party", user_id)

        try:
            # Create party
            party, message = await self.party_service.create_party(user_id)

            # Send result message
            await self.message_sender.send_console_msg(
                message,
                font_color=7,  # FONTTYPE_PARTY
            )

            if party:
                logger.info("User %d created party %d", user_id, party.party_id)
                return CommandResult.ok(data={"party_id": party.party_id, "message": message})

            return CommandResult.error(message or "Error al crear la party")

        except Exception as e:
            logger.exception("Error creating party for user %d", user_id)
            await self.message_sender.send_console_msg(
                "Error al crear la party. Intenta nuevamente.",
                font_color=1,  # FONTTYPE_FIGHT (red for errors)
            )
            return CommandResult.error(f"Error al crear la party: {e!s}")
