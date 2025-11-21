"""Handler for PARTY_SET_LEADER packet.

Handles party leadership transfer (leader only).
"""

import logging
from typing import TYPE_CHECKING

from src.network.packet_reader import PacketReader
from src.network.packet_validator import PacketValidator
from src.tasks.task import Task

if TYPE_CHECKING:
    from src.messaging.message_sender import MessageSender
    from src.services.party_service import PartyService

logger = logging.getLogger(__name__)


class TaskPartySetLeader(Task):
    """Handler for transferring party leadership."""

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
        """Execute party leadership transfer task."""
        user_id = self.session_data["user_id"]
        try:
            # Parse packet data
            reader = PacketReader(self.data)
            validator = PacketValidator(reader)

            # Read target username using PacketValidator (UTF-8, same as login)
            target_username = validator.read_string(min_length=1, max_length=20, encoding="utf-8")

            if validator.has_errors() or target_username is None:
                await self.message_sender.send_console_msg(
                    "Debes especificar un nombre de usuario. Uso: /PARTYLIDER <nombre>",
                    font_color=7,  # FONTTYPE_PARTY
                )
                return
                await self.message_sender.send_console_msg(
                    "Debes especificar un nombre de usuario. Uso: /PARTYLIDER <nombre>",
                    font_color=7,  # FONTTYPE_PARTY
                )
                return

            # Transfer leadership
            message = await self.party_service.transfer_leadership(user_id, target_username)

            # Send result message
            await self.message_sender.send_console_msg(
                message,
                font_color=7,  # FONTTYPE_PARTY
            )

            logger.info("User %s transferred leadership to %s", user_id, target_username)

        except Exception:
            logger.exception("Error transferring leadership for user %s", user_id)
            await self.message_sender.send_console_msg(
                "Error al transferir liderazgo. Intenta nuevamente.",
                font_color=1,  # FONTTYPE_FIGHT (red for errors)
            )
