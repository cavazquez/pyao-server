"""Handler for PARTY_KICK packet.

Handles party member kick (leader only).
"""

import logging
from typing import TYPE_CHECKING

from src.network.packet_reader import PacketReader

if TYPE_CHECKING:
    from src.services.party_service import PartyService

logger = logging.getLogger(__name__)


class TaskPartyKick:
    """Handler for kicking party members."""

    def __init__(self, party_service: PartyService, message_sender) -> None:
        """Initialize task with dependencies."""
        self.party_service = party_service
        self.message_sender = message_sender

    async def execute(self, connection, user_id: int, data: bytes) -> None:
        """Execute party kick task.

        Args:
            connection: Client connection
            user_id: User ID doing the kicking (must be leader)
            data: Packet data containing target username
        """
        try:
            # Parse packet data
            reader = PacketReader(data)
            reader.read_byte()  # Skip packet ID

            # Read target username (UTF-16LE string)
            target_username = reader.read_string()

            if not target_username:
                await self.message_sender.send_console_msg(
                    user_id,
                    "Debes especificar un nombre de usuario. Uso: /KICK <nombre>",
                    font_color=7  # FONTTYPE_PARTY
                )
                return

            # Kick member
            message = await self.party_service.kick_member(user_id, target_username)

            # Send result message
            await self.message_sender.send_console_msg(
                user_id,
                message,
                font_color=7  # FONTTYPE_PARTY
            )

            logger.info("User %s kicked %s from party", user_id, target_username)

        except Exception as e:
            logger.exception("Error kicking from party for user %s: %s", user_id, e)
            await self.message_sender.send_console_msg(
                user_id,
                "Error al expulsar miembro. Intenta nuevamente.",
                font_color=1  # FONTTYPE_FIGHT (red for errors)
            )
