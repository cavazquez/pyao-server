"""Models for Clan/Guild System.

Based on AO VB6 server implementation (clsClan.cls, modGuilds.bas)
"""

import time
from dataclasses import dataclass, field
from enum import IntEnum

# Constants from VB6 server
MAX_CLAN_MEMBERS = 50  # Maximum members per clan
MIN_LEVEL_TO_CREATE = 13  # Minimum level to create a clan
MIN_LEVEL_TO_JOIN = 1  # Minimum level to join a clan
INVITATION_TIMEOUT_SECONDS = 60  # Invitation expiration timeout in seconds
MAX_CLAN_NAME_LENGTH = 30
MAX_CLAN_DESCRIPTION_LENGTH = 200


class ClanRank(IntEnum):
    """Clan member ranks (hierarchical system)."""

    MEMBER = 1  # Regular member
    OFFICER = 2  # Officer (can invite/kick members)
    VICE_LEADER = 3  # Vice leader (can manage most things)
    LEADER = 4  # Leader (full control)


@dataclass
class ClanMember:
    """Represents a clan member.

    Based on tClanMember from VB6 server.
    """

    user_id: int
    username: str
    level: int
    rank: ClanRank = ClanRank.MEMBER
    joined_at: float = field(default_factory=time.time)
    is_online: bool = True
    last_seen: float = field(default_factory=time.time)
    contribution: int = 0  # Contribution points to the clan

    def can_invite_members(self) -> bool:
        """Check if member can invite other members."""
        return self.rank >= ClanRank.OFFICER

    def can_kick_members(self) -> bool:
        """Check if member can kick other members."""
        return self.rank >= ClanRank.OFFICER

    def can_promote_demote(self) -> bool:
        """Check if member can promote/demote other members."""
        return self.rank >= ClanRank.VICE_LEADER

    def can_manage_clan(self) -> bool:
        """Check if member can manage clan settings."""
        return self.rank >= ClanRank.LEADER


@dataclass
class ClanInvitation:
    """Represents a clan invitation.

    Based on tClanInvitation from VB6 server.
    """

    clan_id: int
    clan_name: str
    inviter_id: int
    inviter_username: str
    target_id: int
    target_username: str
    created_at: float = field(default_factory=time.time)
    expires_at: float = field(default_factory=lambda: time.time() + INVITATION_TIMEOUT_SECONDS)

    def is_expired(self) -> bool:
        """Check if invitation has expired."""
        return time.time() > self.expires_at


@dataclass
class Clan:
    """Represents a clan/guild.

    Based on clsClan from VB6 server.
    """

    clan_id: int
    name: str
    description: str = ""
    leader_id: int = 0
    leader_username: str = ""
    members: dict[int, ClanMember] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    gold: int = 0  # Clan treasury gold
    website: str = ""
    news: str = ""  # Clan news/announcements
    # Relationships with other clans
    alliances: set[int] = field(default_factory=set)  # Clan IDs that are allies
    wars: set[int] = field(default_factory=set)  # Clan IDs that are at war
    peace_treaties: set[int] = field(default_factory=set)  # Clan IDs with peace treaties

    def __post_init__(self) -> None:
        """Initialize clan with leader as first member."""
        if self.leader_id > 0:
            leader_member = ClanMember(
                user_id=self.leader_id,
                username=self.leader_username,
                level=1,  # Will be updated when adding
                rank=ClanRank.LEADER,
            )
            self.members[self.leader_id] = leader_member

    @property
    def member_count(self) -> int:
        """Get current number of members."""
        return len(self.members)

    @property
    def is_full(self) -> bool:
        """Check if clan is at maximum capacity.

        Returns:
            bool: True if clan is full, False otherwise.
        """
        return self.member_count >= MAX_CLAN_MEMBERS

    def get_member(self, user_id: int) -> ClanMember | None:
        """Get member by user_id.

        Args:
            user_id: User ID of the member.

        Returns:
            ClanMember if found, None otherwise.
        """
        return self.members.get(user_id)

    def add_member(self, member: ClanMember) -> bool:
        """Add a new member to the clan.

        Args:
            member: ClanMember to add.

        Returns:
            bool: True if added successfully, False if clan is full.
        """
        if self.is_full:
            return False
        self.members[member.user_id] = member
        return True

    def remove_member(self, user_id: int) -> bool:
        """Remove a member from the clan.

        Args:
            user_id: User ID of the member to remove.

        Returns:
            bool: True if removed successfully, False if member not found.
        """
        if user_id not in self.members:
            return False
        # Cannot remove the leader
        if self.members[user_id].rank == ClanRank.LEADER:
            return False
        del self.members[user_id]
        return True

    def update_member_rank(self, user_id: int, new_rank: ClanRank) -> bool:
        """Update a member's rank.

        Args:
            user_id: User ID of the member.
            new_rank: New rank to assign.

        Returns:
            bool: True if updated successfully, False otherwise.
        """
        if user_id not in self.members:
            return False
        # Cannot change leader's rank
        if self.members[user_id].rank == ClanRank.LEADER:
            return False
        # Cannot promote to leader (must transfer leadership)
        if new_rank == ClanRank.LEADER:
            return False
        self.members[user_id].rank = new_rank
        return True

    def transfer_leadership(self, new_leader_id: int) -> bool:
        """Transfer leadership to another member.

        Args:
            new_leader_id: User ID of the new leader.

        Returns:
            bool: True if transferred successfully, False otherwise.
        """
        if new_leader_id not in self.members:
            return False
        if self.members[new_leader_id].rank == ClanRank.LEADER:
            return False  # Already leader

        # Demote old leader to vice leader
        if self.leader_id in self.members:
            self.members[self.leader_id].rank = ClanRank.VICE_LEADER

        # Promote new leader
        self.members[new_leader_id].rank = ClanRank.LEADER
        self.leader_id = new_leader_id
        self.leader_username = self.members[new_leader_id].username
        return True

    def add_alliance(self, clan_id: int) -> None:
        """Add an alliance with another clan.

        Args:
            clan_id: ID of the clan to ally with.
        """
        self.alliances.add(clan_id)
        # Remove from wars and peace treaties if present
        self.wars.discard(clan_id)
        self.peace_treaties.discard(clan_id)

    def remove_alliance(self, clan_id: int) -> None:
        """Remove an alliance with another clan.

        Args:
            clan_id: ID of the clan to remove alliance from.
        """
        self.alliances.discard(clan_id)

    def declare_war(self, clan_id: int) -> None:
        """Declare war on another clan.

        Args:
            clan_id: ID of the clan to declare war on.
        """
        self.wars.add(clan_id)
        # Remove from alliances and peace treaties
        self.alliances.discard(clan_id)
        self.peace_treaties.discard(clan_id)

    def end_war(self, clan_id: int) -> None:
        """End war with another clan.

        Args:
            clan_id: ID of the clan to end war with.
        """
        self.wars.discard(clan_id)

    def add_peace_treaty(self, clan_id: int) -> None:
        """Add a peace treaty with another clan.

        Args:
            clan_id: ID of the clan to make peace with.
        """
        self.peace_treaties.add(clan_id)
        # Remove from wars
        self.wars.discard(clan_id)

    def remove_peace_treaty(self, clan_id: int) -> None:
        """Remove a peace treaty with another clan.

        Args:
            clan_id: ID of the clan to remove peace treaty from.
        """
        self.peace_treaties.discard(clan_id)

    def is_ally(self, clan_id: int) -> bool:
        """Check if another clan is an ally.

        Args:
            clan_id: ID of the clan to check.

        Returns:
            bool: True if ally, False otherwise.
        """
        return clan_id in self.alliances

    def is_at_war(self, clan_id: int) -> bool:
        """Check if at war with another clan.

        Args:
            clan_id: ID of the clan to check.

        Returns:
            bool: True if at war, False otherwise.
        """
        return clan_id in self.wars

    def has_peace_treaty(self, clan_id: int) -> bool:
        """Check if has peace treaty with another clan.

        Args:
            clan_id: ID of the clan to check.

        Returns:
            bool: True if has peace treaty, False otherwise.
        """
        return clan_id in self.peace_treaties
