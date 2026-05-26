"""Shared helpers for clan service mixins."""

import logging
from typing import TYPE_CHECKING

from src.models.clan import ClanRank
from src.services.clan._base import ClanServiceMixinBase

if TYPE_CHECKING:
    from src.messaging.message_sender import MessageSender

logger = logging.getLogger(__name__)

CLAN_RANK_NAMES = {
    ClanRank.MEMBER: "Miembro",
    ClanRank.OFFICER: "Oficial",
    ClanRank.VICE_LEADER: "Vice Líder",
    ClanRank.LEADER: "Líder",
}


class ClanServiceHelpersMixin(ClanServiceMixinBase):
    """Lookup helpers for online players and rank labels."""

    def _get_player_message_sender(self, user_id: int) -> MessageSender | None:
        """Get MessageSender for a specific player from MapManager.

        Returns:
            MessageSender if player found, None otherwise.
        """
        if not self.map_manager:
            return None
        return self.map_manager.get_player_message_sender(user_id)

    def _find_player_by_username(self, username: str) -> int | None:
        """Find player user_id by username from MapManager.

        Args:
            username: Username to search for

        Returns:
            user_id if found, None otherwise
        """
        if not self.map_manager:
            logger.warning("MapManager not available for username search")
            return None

        user_id = self.map_manager.find_player_by_username(username)
        if user_id:
            logger.info("Found player '%s' with user_id=%s", username, user_id)
        else:
            logger.warning("Player '%s' not found in any map", username)
        return user_id
