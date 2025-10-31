"""Handler for PARTY_CREATE packet.

Handles /CREARPARTY command - creates a new party.
"""

import logging
from typing import TYPE_CHECKING

from src.tasks.task import Task

if TYPE_CHECKING:
    from src.services.party_service import PartyService

logger = logging.getLogger(__name__)


class TaskPartyCreate(Task):
    """Handler for creating a new party."""

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
        """Execute party creation task."""
        try:
            # Get user_id from session
            user_id = self.session_data.get("user_id")
            if not user_id:
                await self.message_sender.send_console_msg(
                    "Error: No estás autenticado.", font_color=1
                )
                return

            # Create party
            party, message = await self.party_service.create_party(user_id)

            # Send result message
            await self.message_sender.send_console_msg(
                message,
                font_color=7  # FONTTYPE_PARTY
            )

            if party:
                logger.info(f"User {user_id} created party {party.party_id}")

        except Exception:
            logger.exception("Error creating party for user")
            await self.message_sender.send_console_msg(
                "Error al crear la party. Intenta nuevamente.",
                font_color=1  # FONTTYPE_FIGHT (red for errors)
            )
