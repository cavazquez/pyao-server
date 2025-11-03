"""Handler for PARTY_MESSAGE packet.

Handles /PMSG command - sends message to party members.
"""

import logging
from typing import TYPE_CHECKING

from src.network.packet_reader import PacketReader
from src.tasks.task import Task

if TYPE_CHECKING:
    from src.messaging.message_sender import MessageSender
    from src.services.party_service import PartyService

logger = logging.getLogger(__name__)


class TaskPartyMessage(Task):
    """Handler for sending party messages."""

    def __init__(
        self,
        data: bytes,
        message_sender: MessageSender,
        party_service: PartyService,
        session_data: dict[str, int],
    ) -> None:
        """Initialize task with dependencies."""
        self.data = data
        self.message_sender = message_sender
        self.party_service = party_service
        self.session_data = session_data

    async def execute(self) -> None:
        """Execute party message task."""
        user_id = self.session_data["user_id"]

        try:
            # Parse packet data
            reader = PacketReader(self.data)
            reader.read_byte()  # Skip packet ID

            # Read message (UTF-16LE string)
            message = reader.read_string()

            if not message:
                await self.message_sender.send_console_msg(
                    "Debes especificar un mensaje. Uso: /PMSG <mensaje>",
                    font_color=7,  # FONTTYPE_PARTY
                )
                return

            # Send party message
            result = await self.party_service.send_party_message(user_id, message)

            # If there's an error message, send it to sender
            if result:
                await self.message_sender.send_console_msg(
                    result,
                    font_color=7,  # FONTTYPE_PARTY
                )

            logger.info("User %s sent party message: %s...", user_id, message[:50])

        except Exception:
            logger.exception("Error sending party message for user %s", user_id)
            await self.message_sender.send_console_msg(
                "Error al enviar mensaje a la party. Intenta nuevamente.",
                font_color=1,  # FONTTYPE_FIGHT (red for errors)
            )
