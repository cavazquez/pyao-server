"""Clan Service - Business logic for clan/guild system."""

from typing import TYPE_CHECKING

from src.services.clan.creation import ClanCreationMixin
from src.services.clan.membership import ClanMembershipMixin
from src.services.clan.messaging import ClanMessagingMixin
from src.services.clan.ranks import ClanRankMixin

if TYPE_CHECKING:
    from src.game.map_manager import MapManager
    from src.messaging.broadcast_service import BroadcastService
    from src.messaging.message_sender import MessageSender
    from src.repositories.clan_repository import ClanRepository
    from src.repositories.player_repository import PlayerRepository


class ClanService(
    ClanCreationMixin,
    ClanMembershipMixin,
    ClanRankMixin,
    ClanMessagingMixin,
):
    """Service for managing clan operations."""

    def __init__(
        self,
        clan_repository: ClanRepository,
        player_repository: PlayerRepository,
        message_sender: MessageSender,
        broadcast_service: BroadcastService | None = None,
        map_manager: MapManager | None = None,
    ) -> None:
        """Initialize clan service with dependencies."""
        self.clan_repo = clan_repository
        self.player_repo = player_repository
        self.message_sender = message_sender
        self.broadcast_service = broadcast_service
        self.map_manager = map_manager
