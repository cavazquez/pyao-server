"""Handler for PARTY_JOIN packet.

Handles /PARTY command - invites a user to party.
"""

import logging
from typing import TYPE_CHECKING

from src.network.packet_reader import PacketReader
from src.tasks.task import Task

if TYPE_CHECKING:
    from src.messaging.message_sender import MessageSender
    from src.services.party_service import PartyService

logger = logging.getLogger(__name__)


class TaskPartyJoin(Task):
    """Handler for inviting users to party."""

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
        """Execute party join (invite) task."""
        logger.info("TaskPartyJoin.execute() called with data length: %d", len(self.data))

        user_id = self.session_data.get("user_id")
        if not user_id:
            await self.message_sender.send_console_msg("Error: No estás autenticado.", font_color=1)
            return

        try:
            # Parse packet data
            reader = PacketReader(self.data)
            # NO llamar read_byte() - PacketReader ya salta el packet ID en __init__

            logger.info("Party invite packet data (hex): %s", self.data.hex())
            logger.info("Party invite packet data (raw): %s", self.data)

            # Read target username (cliente Godot envía ASCII/Latin-1)
            target_username = reader.read_ascii_string()
            logger.info("Decoded username (ASCII): '%s'", target_username)

            if not target_username:
                await self.message_sender.send_console_msg(
                    "Debes especificar un nombre de usuario. Uso: /PARTY <nombre>", font_color=7
                )
                return

            # Send invitation
            message = await self.party_service.invite_to_party(user_id, target_username)

            # Send result message
            await self.message_sender.send_console_msg(message, font_color=7)

            logger.info("User %s invited %s to party", user_id, target_username)

        except Exception:
            logger.exception("Error inviting to party")
            await self.message_sender.send_console_msg(
                "Error al invitar a la party. Intenta nuevamente.", font_color=1
            )
