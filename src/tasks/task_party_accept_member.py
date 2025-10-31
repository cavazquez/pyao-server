"""Handler for PARTY_ACCEPT_MEMBER packet.

Handles /ACCEPTPARTY command - accepts a party invitation.
"""

import logging
from typing import TYPE_CHECKING

from src.network.packet_reader import PacketReader
from src.tasks.task import Task

if TYPE_CHECKING:
    from src.services.party_service import PartyService

logger = logging.getLogger(__name__)


class TaskPartyAcceptMember(Task):
    """Handler for accepting party invitations."""

    def __init__(
        self,
        data: bytes,
        message_sender,
        party_service: "PartyService",
        session_data: dict,
    ) -> None:
        """Initialize task with dependencies."""
        super().__init__(data, message_sender)
        self.party_service = party_service
        self.session_data = session_data

    async def execute(self) -> None:
        """Execute party acceptance task."""
        user_id = self.session_data.get("user_id")
        if not user_id:
            await self.message_sender.send_console_msg(
                "Error: No estás autenticado.", font_color=1
            )
            return

        try:
            # Parse packet data
            logger.info(f"Accept party packet data (hex): {self.data.hex()}")
            logger.info(f"Accept party packet data (raw): {self.data}")
            
            # The packet format is: [packet_id:1][length:2][string:N]
            # Skip packet ID (byte 0) and length (bytes 1-2), read only the string part
            leader_username = self.data[3:].decode('ascii').strip().rstrip('\x00')
            logger.info(f"User {user_id} trying to accept party from '{leader_username}'")

            if not leader_username:
                await self.message_sender.send_console_msg(
                    "Debes especificar el nombre del líder de la party. Uso: /ACCEPTPARTY <nombre>",
                    font_color=7
                )
                return

            # Get user's pending invitations to find the right party
            invitations = await self.party_service.get_user_invitations(user_id)
            logger.info(f"User {user_id} has {len(invitations)} pending invitations")
            target_invitation = None

            for invitation in invitations:
                logger.info(f"  Invitation from '{invitation.inviter_username}' (party {invitation.party_id})")
                if invitation.inviter_username.lower() == leader_username.lower():
                    target_invitation = invitation
                    logger.info(f"  -> Match found!")
                    break

            if not target_invitation:
                logger.warning(f"No matching invitation found for '{leader_username}'")
                await self.message_sender.send_console_msg(
                    f"No tienes una invitación pendiente de {leader_username}",
                    font_color=7
                )
                return

            # Accept invitation
            message = await self.party_service.accept_invitation(user_id, target_invitation.party_id)

            # Send result message
            await self.message_sender.send_console_msg(
                message,
                font_color=7
            )

            logger.info(f"User {user_id} accepted party invitation from {leader_username}")

        except Exception:
            logger.exception("Error accepting party invitation")
            await self.message_sender.send_console_msg(
                "Error al aceptar la invitación. Intenta nuevamente.",
                font_color=1
            )
