"""Clan service mixins."""

import logging

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
        # Get sender's clan
        clan = await self.clan_repo.get_user_clan(sender_id)
        if not clan:
            return "No perteneces a ningún clan"

        # Get sender member info
        sender_member = clan.get_member(sender_id)
        if not sender_member:
            return "Error: no se encontró tu información en el clan"

        sender_username = sender_member.username
        logger.info(
            "Clan message from %s (ID:%s) in clan '%s': '%s'",
            sender_username,
            sender_id,
            clan.name,
            message,
        )

        # Send message to all clan members
        if self.map_manager:
            for member_id in clan.members:
                member_sender = self._get_player_message_sender(member_id)
                if member_sender:
                    full_message = f"[Clan] {sender_username}: {message}"
                    logger.debug("Sending clan message to member %s: '%s'", member_id, full_message)
                    await member_sender.send_console_msg(
                        full_message,
                        font_color=7,  # FONTTYPE_PARTY (verde para clan)
                    )

        return ""
