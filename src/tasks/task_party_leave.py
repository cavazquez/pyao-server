"""Handler for PARTY_LEAVE packet.

Handles /SALIRPARTY command - leaves current party.
"""

import logging
from typing import TYPE_CHECKING

from src.tasks.task import Task

if TYPE_CHECKING:
    from src.messaging.message_sender import MessageSender
    from src.services.party_service import PartyService

logger = logging.getLogger(__name__)


class TaskPartyLeave(Task):
    """Handler for leaving a party."""

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
        """Execute party leave task."""
        try:
            # Get user_id from session
            user_id = self.session_data.get("user_id")
            if not user_id:
                await self.message_sender.send_console_msg(  # type: ignore[call-arg]
                    0, "Error: No estás autenticado.", font_color=1
                )
                return

            # Leave party
            message = await self.party_service.leave_party(user_id)

            # Send result message
            await self.message_sender.send_console_msg(message, font_color=7)  # type: ignore[call-arg]

            logger.info("User %s left party", user_id)

        except Exception:
            logger.exception("Error leaving party")
            await self.message_sender.send_console_msg(  # type: ignore[call-arg]
                "Error al abandonar la party. Intenta nuevamente.", font_color=1
            )
