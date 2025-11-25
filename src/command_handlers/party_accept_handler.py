"""Handler para comando de aceptar invitación a party."""

import logging
from typing import TYPE_CHECKING

from src.commands.base import Command, CommandHandler, CommandResult
from src.commands.party_accept_command import PartyAcceptCommand

if TYPE_CHECKING:
    from src.messaging.message_sender import MessageSender
    from src.services.party_service import PartyService

logger = logging.getLogger(__name__)


class PartyAcceptCommandHandler(CommandHandler):
    """Handler para comando de aceptar invitación a party (solo lógica de negocio)."""

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
        """Ejecuta el comando de aceptar invitación (solo lógica de negocio).

        Args:
            command: Comando de aceptar invitación.

        Returns:
            Resultado de la ejecución.
        """
        if not isinstance(command, PartyAcceptCommand):
            return CommandResult.error("Comando inválido: se esperaba PartyAcceptCommand")

        user_id = command.user_id
        leader_username = command.leader_username

        logger.info(
            "PartyAcceptCommandHandler: user_id=%d intenta aceptar invitación de '%s'",
            user_id,
            leader_username,
        )

        try:
            # Get user's pending invitations to find the right party
            invitations = await self.party_service.get_user_invitations(user_id)
            logger.info("User %d has %d pending invitations", user_id, len(invitations))
            target_invitation = None

            for invitation in invitations:
                logger.info(
                    "Invitation from leader: %s (party %d)",
                    invitation.inviter_username,
                    invitation.party_id,
                )
                if invitation.inviter_username.lower() == leader_username.lower():
                    target_invitation = invitation
                    logger.info("  -> Match found!")
                    break

            if not target_invitation:
                logger.warning("No matching invitation found for '%s'", leader_username)
                await self.message_sender.send_console_msg(
                    f"No tienes una invitación pendiente de {leader_username}", font_color=7
                )
                return CommandResult.error(
                    f"No tienes una invitación pendiente de {leader_username}"
                )

            # Accept invitation
            message = await self.party_service.accept_invitation(
                user_id, target_invitation.party_id
            )

            # Send result message
            await self.message_sender.send_console_msg(message, font_color=7)

            logger.info("User %s accepted party invitation from %s", user_id, leader_username)

            return CommandResult.ok(
                data={
                    "party_id": target_invitation.party_id,
                    "leader_username": leader_username,
                    "message": message,
                }
            )

        except Exception as e:
            logger.exception("Error accepting party invitation")
            await self.message_sender.send_console_msg(
                "Error al aceptar la invitación. Intenta nuevamente.", font_color=1
            )
            return CommandResult.error(f"Error al aceptar la invitación: {e!s}")
