"""Handler for PARTY_JOIN packet.

Handles /PARTY command - invites a user to party.
"""

import logging
from typing import TYPE_CHECKING

from src.tasks.task import Task
from src.network.packet_reader import PacketReader

if TYPE_CHECKING:
    from src.services.party_service import PartyService

logger = logging.getLogger(__name__)


class TaskPartyJoin(Task):
    """Handler for inviting users to party."""

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
        """Execute party join (invite) task."""
        logger.info(f"TaskPartyJoin.execute() called with data length: {len(self.data)}")
        
        user_id = self.session_data.get("user_id")
        if not user_id:
            await self.message_sender.send_console_msg(
                "Error: No estás autenticado.", font_color=1
            )
            return

        try:
            # Parse packet data
            logger.info(f"Party invite packet data (hex): {self.data.hex()}")
            logger.info(f"Party invite packet data (raw): {self.data}")
            
            # Check if packet has data beyond packet ID
            if len(self.data) <= 1:
                await self.message_sender.send_console_msg(
                    "Debes especificar un nombre de usuario. Uso: /PARTY <nombre>",
                    font_color=7
                )
                return
            
            # The packet format is: [packet_id:1][length:4][string:N]
            # Skip packet ID (byte 0) and length (bytes 1-4), read only the string part
            # Skip first 5 bytes (packet_id + int32 length)
            target_username = self.data[5:].decode('ascii').strip().rstrip('\x00')
            logger.info(f"Decoded username (ASCII): '{target_username}'")

            if not target_username:
                await self.message_sender.send_console_msg(
                    "Debes especificar un nombre de usuario. Uso: /PARTY <nombre>",
                    font_color=7
                )
                return

            # Send invitation
            message = await self.party_service.invite_to_party(user_id, target_username)

            # Send result message
            await self.message_sender.send_console_msg(
                message,
                font_color=7
            )

            logger.info(f"User {user_id} invited {target_username} to party")

        except Exception:
            logger.exception("Error inviting to party")
            await self.message_sender.send_console_msg(
                "Error al invitar a la party. Intenta nuevamente.",
                font_color=1
            )
