"""Party Service - Business logic for party system.

Based on AO VB6 server implementation (mdParty.bas)
"""

import logging
from typing import TYPE_CHECKING

from src.network.chat_channel import deliver_chat
from src.security.chat_mutes import chat_rejection

logger = logging.getLogger(__name__)


if TYPE_CHECKING:
    from src.services.party_service import PartyService


class MessagingComponent:
    """Coordina messaging sin cambiar la fachada existente."""

    def __init__(self, owner: PartyService) -> None:
        """Conserva el contexto y las dependencias del servicio propietario."""
        self.owner = owner

    async def send_party_message(self, sender_id: int, message: str) -> str:
        """Send message to all party members.

        Returns:
            Result message to send to sender
        """
        rejection = await chat_rejection(self.owner.party_repo.redis.redis, sender_id, "party")
        if rejection:
            return rejection
        # Get sender's party
        party = await self.owner.party_repo.get_user_party(sender_id)
        if not party or not party.is_member(sender_id):
            return "No eres miembro de ninguna party"

        # Get sender username from account
        sender_username = f"Usuario#{sender_id}"
        if self.owner.account_repo:
            account_data = await self.owner.account_repo.get_account_by_user_id(sender_id)
            if account_data:
                sender_username = account_data.get("username", sender_username)
        logger.debug("Chat de party enviado por user_id=%d", sender_id)

        # Send message to all members
        if self.owner.map_manager:
            for member_id in party.member_ids:
                member_sender = self.owner.get_player_message_sender(member_id)
                if member_sender:
                    full_message = f"[Party] {sender_username}: {message}"
                    await deliver_chat(
                        member_sender,
                        "party",
                        sender_id,
                        sender_username,
                        message,
                        legacy=full_message,
                        context=str(party.party_id),
                        font=7,
                    )

        return ""
