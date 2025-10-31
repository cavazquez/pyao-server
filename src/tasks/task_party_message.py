"""Handler for PARTY_MESSAGE packet.

Handles /PMSG command - sends message to party members.
"""

import logging
from typing import TYPE_CHECKING

from src.network.packet_reader import PacketReader

if TYPE_CHECKING:
    from src.services.party_service import PartyService

logger = logging.getLogger(__name__)


class TaskPartyMessage:
    """Handler for sending party messages."""

    def __init__(self, party_service: PartyService, message_sender) -> None:
        """Initialize task with dependencies."""
        self.party_service = party_service
        self.message_sender = message_sender

    async def execute(self, connection, user_id: int, data: bytes) -> None:
        """Execute party message task.

        Args:
            connection: Client connection
            user_id: User ID sending the message
            data: Packet data containing message text
        """
        try:
            # Parse packet data
            reader = PacketReader(data)
            reader.read_byte()  # Skip packet ID

            # Read message (UTF-16LE string)
            message = reader.read_string()

            if not message:
                await self.message_sender.send_console_msg(
                    user_id,
                    "Debes especificar un mensaje. Uso: /PMSG <mensaje>",
                    font_color=7  # FONTTYPE_PARTY
                )
                return

            # Send party message
            result = await self.party_service.send_party_message(user_id, message)

            # If there's an error message, send it to sender
            if result:
                await self.message_sender.send_console_msg(
                    user_id,
                    result,
                    font_color=7  # FONTTYPE_PARTY
                )

            logger.info(f"User {user_id} sent party message: {message[:50]}...")

        except Exception as e:
            logger.exception("Error sending party message for user %s: %s", user_id, e)
            await self.message_sender.send_console_msg(
                user_id,
                "Error al enviar mensaje a la party. Intenta nuevamente.",
                font_color=1  # FONTTYPE_FIGHT (red for errors)
            )
