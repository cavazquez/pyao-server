"""Handler for PARTY_SET_LEADER packet.

Handles party leadership transfer (leader only).
"""

import logging
from typing import TYPE_CHECKING

from src.network.packet_reader import PacketReader

if TYPE_CHECKING:
    from src.messaging.message_sender import MessageSender
    from src.network.client_connection import ClientConnection
    from src.services.party_service import PartyService

logger = logging.getLogger(__name__)


class TaskPartySetLeader:
    """Handler for transferring party leadership."""

    def __init__(self, party_service: PartyService, message_sender: MessageSender) -> None:
        """Initialize task with dependencies."""
        self.party_service = party_service
        self.message_sender = message_sender

    async def execute(self, _connection: ClientConnection, user_id: int, data: bytes) -> None:
        """Execute party leadership transfer task.

        Args:
            _connection: Client connection (unused)
            user_id: User ID transferring leadership (must be current leader)
            data: Packet data containing target username
        """
        try:
            # Parse packet data
            reader = PacketReader(data)
            reader.read_byte()  # Skip packet ID

            # Read target username (UTF-16LE string)
            target_username = reader.read_string()

            if not target_username:
                await self.message_sender.send_console_msg(  # type: ignore[call-arg]
                    user_id,
                    "Debes especificar un nombre de usuario. Uso: /PARTYLIDER <nombre>",
                    font_color=7,  # FONTTYPE_PARTY
                )
                return

            # Transfer leadership
            message = await self.party_service.transfer_leadership(user_id, target_username)

            # Send result message
            await self.message_sender.send_console_msg(  # type: ignore[call-arg]
                user_id,
                message,
                font_color=7,  # FONTTYPE_PARTY
            )

            logger.info("User %s transferred leadership to %s", user_id, target_username)

        except Exception:
            logger.exception("Error transferring leadership for user %s", user_id)
            await self.message_sender.send_console_msg(  # type: ignore[call-arg]
                user_id,
                "Error al transferir liderazgo. Intenta nuevamente.",
                font_color=1,  # FONTTYPE_FIGHT (red for errors)
            )
