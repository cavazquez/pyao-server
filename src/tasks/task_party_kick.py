"""Handler for PARTY_KICK packet.

Handles party member kick (leader only).
"""

import logging
from typing import TYPE_CHECKING

from src.network.packet_reader import PacketReader
from src.tasks.task import Task

if TYPE_CHECKING:
    from src.messaging.message_sender import MessageSender
    from src.services.party_service import PartyService

logger = logging.getLogger(__name__)


class TaskPartyKick(Task):
    """Handler for kicking party members."""

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
        """Execute party kick task."""
        user_id = self.session_data["user_id"]
        try:
            # Parse packet data
            reader = PacketReader(self.data)
            reader.read_byte()  # Skip packet ID

            # Read target username (UTF-16LE string)
            target_username = reader.read_string()

            if not target_username:
                await self.message_sender.send_console_msg(
                    "Debes especificar un nombre de usuario. Uso: /KICK <nombre>",
                    font_color=7,  # FONTTYPE_PARTY
                )
                return

            # Kick member
            message = await self.party_service.kick_member(user_id, target_username)

            # Send result message
            await self.message_sender.send_console_msg(
                message,
                font_color=7,  # FONTTYPE_PARTY
            )

            logger.info("User %s kicked %s from party", user_id, target_username)

        except Exception:
            logger.exception("Error kicking from party for user %s", user_id)
            await self.message_sender.send_console_msg(
                "Error al expulsar miembro. Intenta nuevamente.",
                font_color=1,  # FONTTYPE_FIGHT (red for errors)
            )
