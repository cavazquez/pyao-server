"""Handler for PARTY_ACCEPT_MEMBER packet.

Handles /ACCEPTPARTY command - accepts a party invitation.
"""

import logging
from typing import TYPE_CHECKING

from src.tasks.task import Task

if TYPE_CHECKING:
    from src.messaging.message_sender import MessageSender
    from src.services.party_service import PartyService

logger = logging.getLogger(__name__)


class TaskPartyAcceptMember(Task):
    """Handler for accepting party invitations."""

    def __init__(
        self,
        data: bytes,
        message_sender: MessageSender,
        party_service: PartyService,
        session_data: dict[str, int],
    ) -> None:
        """Initialize task with dependencies."""
        super().__init__(data, message_sender)
        self.party_service = party_service
        self.session_data = session_data

    async def execute(self) -> None:
        """Execute party acceptance task."""
        user_id = self.session_data.get("user_id")
        if not user_id:
            await self.message_sender.send_console_msg("Error: No estás autenticado.", font_color=1)
            return

        try:
            # Parse packet data
            logger.info("Accept party packet data (hex): %s", self.data.hex())
            logger.info("Accept party packet data (raw): %s", self.data)

            # The packet format is: [packet_id:1][length:2][string:N]
            # Skip packet ID (byte 0) and length (bytes 1-2), read only the string part
            leader_username = self.data[3:].decode("ascii").strip().rstrip("\x00")
            logger.info("User %s trying to accept party from '%s'", user_id, leader_username)

            if not leader_username:
                await self.message_sender.send_console_msg(
                    "Debes especificar el nombre del líder de la party. Uso: /ACCEPTPARTY <nombre>",
                    font_color=7,
                )
                return

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
                return

            # Accept invitation
            message = await self.party_service.accept_invitation(
                user_id, target_invitation.party_id
            )

            # Send result message
            await self.message_sender.send_console_msg(message, font_color=7)

            logger.info("User %s accepted party invitation from %s", user_id, leader_username)

        except Exception:
            logger.exception("Error accepting party invitation")
            await self.message_sender.send_console_msg(
                "Error al aceptar la invitación. Intenta nuevamente.", font_color=1
            )
