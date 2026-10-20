"""Clan service mixins."""

import logging

from src.network.chat_channel import deliver_chat
from src.security.chat_mutes import chat_rejection
from src.services.clan._helpers import ClanServiceHelpersMixin

logger = logging.getLogger(__name__)


class ClanMessagingMixin(ClanServiceHelpersMixin):
    """Broadcast messages to all clan members."""

    async def send_clan_message(self, sender_id: int, message: str) -> str:
        """Send message to all clan members.

        Args:
            sender_id: User ID of the message sender.
            message: Message content.

        Returns:
            Error message if failed, empty string if successful.
        """
        rejection = await chat_rejection(self.clan_repo.redis.redis, sender_id, "clan")
        if rejection:
            return rejection
        # Get sender's clan
        clan = await self.clan_repo.get_user_clan(sender_id)
        if not clan:
            return "No perteneces a ningún clan"

        # Get sender member info
        sender_member = clan.get_member(sender_id)
        if not sender_member:
            return "Error: no se encontró tu información en el clan"

        sender_username = sender_member.username
        logger.debug("Chat de clan enviado por user_id=%d", sender_id)

        # Send message to all clan members
        if self.map_manager:
            for member_id in clan.members:
                member_sender = self._get_player_message_sender(member_id)
                if member_sender:
                    full_message = f"[Clan] {sender_username}: {message}"
                    await deliver_chat(
                        member_sender,
                        "clan",
                        sender_id,
                        sender_username,
                        message,
                        legacy=full_message,
                        context=str(clan.clan_id),
                        font=7,
                    )

        return ""
