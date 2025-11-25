"""Handler para comando de expulsar miembro de party."""

import logging
from typing import TYPE_CHECKING

from src.commands.base import Command, CommandHandler, CommandResult
from src.commands.party_kick_command import PartyKickCommand

if TYPE_CHECKING:
    from src.messaging.message_sender import MessageSender
    from src.services.party_service import PartyService

logger = logging.getLogger(__name__)


class PartyKickCommandHandler(CommandHandler):
    """Handler para comando de expulsar miembro de party (solo lógica de negocio)."""

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
        """Ejecuta el comando de expulsar miembro (solo lógica de negocio).

        Args:
            command: Comando de expulsar miembro.

        Returns:
            Resultado de la ejecución.
        """
        if not isinstance(command, PartyKickCommand):
            return CommandResult.error("Comando inválido: se esperaba PartyKickCommand")

        user_id = command.user_id
        target_username = command.target_username

        logger.info(
            "PartyKickCommandHandler: user_id=%d intenta expulsar a '%s'", user_id, target_username
        )

        try:
            # Kick member
            message = await self.party_service.kick_member(user_id, target_username)

            # Send result message
            await self.message_sender.send_console_msg(
                message,
                font_color=7,  # FONTTYPE_PARTY
            )

            logger.info("User %s kicked %s from party", user_id, target_username)

            return CommandResult.ok(data={"target_username": target_username, "message": message})

        except Exception as e:
            logger.exception("Error kicking from party for user %s", user_id)
            await self.message_sender.send_console_msg(
                "Error al expulsar miembro. Intenta nuevamente.",
                font_color=1,  # FONTTYPE_FIGHT (red for errors)
            )
            return CommandResult.error(f"Error al expulsar miembro: {e!s}")
