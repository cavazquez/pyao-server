"""Party Service - Business logic for party system.

Based on AO VB6 server implementation (mdParty.bas)
"""

import logging
from typing import TYPE_CHECKING

from src.services.party.creation import CreationComponent
from src.services.party.experience import ExperienceComponent
from src.services.party.invitations import InvitationsComponent
from src.services.party.membership import MembershipComponent
from src.services.party.messaging import MessagingComponent

if TYPE_CHECKING:
    from src.game.map_manager import MapManager
    from src.messaging.broadcast_service import BroadcastService
    from src.messaging.message_sender import MessageSender
    from src.models.party import (
        Party,
        PartyInvitation,
    )
    from src.repositories.account_repository import AccountRepository
    from src.repositories.party_repository import PartyRepository
    from src.repositories.player_repository import PlayerRepository

logger = logging.getLogger(__name__)


class PartyService:
    """Service for managing party operations."""

    def __init__(
        self,
        party_repository: PartyRepository,
        player_repository: PlayerRepository,
        message_sender: MessageSender,
        broadcast_service: BroadcastService | None = None,
        map_manager: MapManager | None = None,
        account_repo: AccountRepository | None = None,
    ) -> None:
        """Initialize party service with dependencies."""
        self.party_repo = party_repository
        self.player_repo = player_repository
        self.message_sender = message_sender
        self.broadcast_service = broadcast_service
        self.map_manager = map_manager
        self.account_repo = account_repo
        self._creation = CreationComponent(self)
        self._invitations = InvitationsComponent(self)
        self._membership = MembershipComponent(self)
        self._messaging = MessagingComponent(self)
        self._experience = ExperienceComponent(self)

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

    def get_player_message_sender(self, user_id: int) -> MessageSender | None:
        """Expone la conexión vigente a los componentes de membresía.

        Returns:
            Emisor vigente, si el jugador está conectado.
        """
        return self._get_player_message_sender(user_id)

    def find_player_by_username(self, username: str) -> int | None:
        """Expone la resolución de jugadores a los componentes de membresía.

        Returns:
            Identidad conectada o None.
        """
        return self._find_player_by_username(username)

    async def can_create_party(self, user_id: int) -> tuple[bool, str]:
        """Check if user can create a party.

        Returns:
            Tuple of (can_create, error_message)
        """
        return await self._creation.can_create_party(user_id)

    async def create_party(self, user_id: int, username: str = "") -> tuple[Party | None, str]:
        """Create a new party with user as leader.

        Args:
            user_id: User ID creating the party
            username: Username of the leader (optional, will use "Player{user_id}" if not provided)

        Returns:
            Tuple of (party, error_message)
        """
        return await self._creation.create_party(user_id, username)

    async def can_invite_to_party(
        self, inviter_id: int, target_id: int
    ) -> tuple[bool, str, Party | None]:
        """Check if inviter can invite target to their party.

        Returns:
            Tuple of (can_invite, error_message, party)
        """
        return await self._invitations.can_invite_to_party(inviter_id, target_id)

    async def invite_to_party(self, inviter_id: int, target_username: str) -> str:
        """Invite a user to the inviter's party.

        Returns:
            Result message to send to inviter
        """
        return await self._invitations.invite_to_party(inviter_id, target_username)

    async def can_accept_invitation(
        self, user_id: int, party_id: int
    ) -> tuple[bool, str, Party | None]:
        """Check if user can accept party invitation.

        Returns:
            Tuple of (can_accept, error_message, party)
        """
        return await self._invitations.can_accept_invitation(user_id, party_id)

    async def accept_invitation(self, user_id: int, party_id: int) -> str:
        """Accept a party invitation.

        Returns:
            Result message to send to user
        """
        return await self._invitations.accept_invitation(user_id, party_id)

    async def leave_party(self, user_id: int) -> str:
        """Leave current party.

        Returns:
            Result message to send to user
        """
        return await self._membership.leave_party(user_id)

    async def kick_member(self, leader_id: int, target_username: str) -> str:
        """Kick a member from party (leader only).

        Returns:
            Result message to send to leader
        """
        return await self._membership.kick_member(leader_id, target_username)

    async def transfer_leadership(self, leader_id: int, target_username: str) -> str:
        """Transfer party leadership to another member.

        Returns:
            Result message to send to leader
        """
        return await self._membership.transfer_leadership(leader_id, target_username)

    async def send_party_message(self, sender_id: int, message: str) -> str:
        """Send message to all party members.

        Returns:
            Result message to send to sender
        """
        return await self._messaging.send_party_message(sender_id, message)

    async def get_party_info(self, user_id: int) -> Party | None:
        """Get party information for user.

        Returns:
            Party object if user is in party, None otherwise
        """
        return await self._membership.get_party_info(user_id)

    async def get_user_invitations(self, user_id: int) -> list[PartyInvitation]:
        """Get all pending invitations for user.

        Returns:
            List of pending party invitations.
        """
        return await self._invitations.get_user_invitations(user_id)

    async def distribute_experience(
        self, earner_id: int, exp_amount: int, map_id: int, x: int, y: int
    ) -> dict[int, float]:
        """Distribute experience to party members within range.

        Args:
            earner_id: ID of the user who earned the experience.
            exp_amount: Amount of experience to distribute.
            map_id: Map ID where experience was earned.
            x: X coordinate where experience was earned.
            y: Y coordinate where experience was earned.

        Returns:
            Dictionary mapping user_id -> experience_amount
        """
        return await self._experience.distribute_experience(earner_id, exp_amount, map_id, x, y)

    async def update_member_level(self, user_id: int, new_level: int) -> bool:
        """Update member's level in their party.

        Returns:
            True if updated successfully, False if not in party
        """
        return await self._experience.update_member_level(user_id, new_level)

    async def set_member_online_status(self, user_id: int, is_online: bool) -> bool:
        """Set online status of party member.

        Returns:
            True if updated successfully, False if not in party
        """
        return await self._experience.set_member_online_status(user_id, is_online)
