"""Models for Party System.

Based on AO VB6 server implementation (clsParty.cls, mdParty.bas)
"""

import math
import time
from dataclasses import dataclass, field

# Constants from VB6 server
MAX_PARTY_MEMBERS = 5  # PARTY_MAXMEMBERS
MIN_LEVEL_TO_CREATE = 1  # MINPARTYLEVEL (temporalmente 1 para testing, original: 15)
MAX_LEVEL_DIFFERENCE = 7  # MAXPARTYDELTALEVEL
MAX_EXP_DISTANCE = 18  # PARTY_MAXDISTANCIA
PARTY_EXPERIENCE_PER_HIT = False  # PARTY_EXPERIENCIAPORGOLPE
LEVEL_EXPONENT = 1.2  # ExponenteNivelParty (configurable)


@dataclass
class PartyMember:
    """Represents a party member.

    Based on tPartyMember from VB6 server.
    """
    user_id: int
    username: str
    level: int
    accumulated_exp: float = 0.0  # Experience accumulated in party
    is_online: bool = True
    last_seen: float = field(default_factory=time.time)

    def add_experience(self, exp_amount: float) -> None:
        """Add experience to this member's accumulated pool."""
        self.accumulated_exp += exp_amount
        self.accumulated_exp = max(self.accumulated_exp, 0)

    def withdraw_experience(self) -> float:
        """Withdraw all accumulated experience and reset to 0."""
        exp = self.accumulated_exp
        self.accumulated_exp = 0.0
        return exp

    def can_receive_experience(self, distance: int) -> bool:
        """Check if member can receive experience based on distance."""
        return self.is_online and distance <= MAX_EXP_DISTANCE


@dataclass
class Party:
    """Represents a party group.

    Based on clsParty from VB6 server.
    """
    party_id: int
    leader_id: int
    leader_username: str
    members: dict[int, PartyMember] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    total_exp_earned: float = 0.0
    sum_elevated_levels: float = 0.0  # For experience distribution

    def __post_init__(self) -> None:
        """Initialize party with leader as first member."""
        leader_member = PartyMember(
            user_id=self.leader_id,
            username=self.leader_username,
            level=1  # Will be updated when adding
        )
        self.members[self.leader_id] = leader_member
        self._update_sum_elevated_levels()

    @property
    def member_count(self) -> int:
        """Get current number of members."""
        return len(self.members)

    @property
    def is_full(self) -> bool:
        """Check if party is at maximum capacity."""
        return self.member_count >= MAX_PARTY_MEMBERS

    @property
    def member_ids(self) -> set[int]:
        """Get set of all member IDs."""
        return set(self.members.keys())

    def is_leader(self, user_id: int) -> bool:
        """Check if user is the leader of this party."""
        return user_id == self.leader_id

    def add_member(self, user_id: int, username: str, level: int) -> bool:
        """Add a new member to the party.

        Args:
            user_id: User ID to add
            username: Username of the user
            level: Current level of the user

        Returns:
            True if added successfully, False if party is full
        """
        if self.is_full or user_id in self.members:
            return False

        # Check level difference with existing members
        if not self._can_join_by_level(level):
            return False

        new_member = PartyMember(
            user_id=user_id,
            username=username,
            level=level
        )

        self.members[user_id] = new_member
        self._update_sum_elevated_levels()
        return True

    def remove_member(self, user_id: int) -> PartyMember | None:
        """Remove a member from the party.

        Args:
            user_id: User ID to remove

        Returns:
            The removed member, or None if user wasn't in party
        """
        member = self.members.pop(user_id, None)
        if member:
            self._update_sum_elevated_levels()
        return member

    def is_member(self, user_id: int) -> bool:
        """Check if user is a member of this party."""
        return user_id in self.members

    def get_member(self, user_id: int) -> PartyMember | None:
        """Get member by user ID."""
        return self.members.get(user_id)

    def can_accept_invitation(self, inviter_id: int) -> bool:
        """Check if inviter can invite (only leader can invite)."""
        return self.is_leader(inviter_id)

    def _can_join_by_level(self, new_level: int) -> bool:
        """Check if user can join based on level differences."""
        for member in self.members.values():
            if abs(member.level - new_level) > MAX_LEVEL_DIFFERENCE:
                return False
        return True

    def _update_sum_elevated_levels(self) -> None:
        """Update sum of elevated levels for experience distribution."""
        self.sum_elevated_levels = sum(
            member.level ** LEVEL_EXPONENT
            for member in self.members.values()
        )

    def distribute_experience(self, total_exp: int, map_id: int, x: int, y: int,
                             get_user_level_func: callable,
                             get_user_position_func: callable,
                             is_user_alive_func: callable) -> dict[int, float]:
        """Distribute experience among eligible members.

        Args:
            total_exp: Total experience to distribute
            map_id: Map where experience was earned
            x, y: Coordinates where experience was earned
            get_user_level_func: Function to get user level by ID
            get_user_position_func: Function to get user position by ID
            is_user_alive_func: Function to check if user is alive

        Returns:
            Dictionary mapping user_id -> experience_amount
        """
        self.total_exp_earned += total_exp
        distributed_exp: dict[int, float] = {}

        if self.sum_elevated_levels <= 0:
            return distributed_exp

        for member in self.members.values():
            # Check if member is eligible for experience
            user_pos = get_user_position_func(member.user_id)
            if not user_pos:
                continue

            if not is_user_alive_func(member.user_id):
                continue

            if user_pos["map"] != map_id:
                continue

            distance = math.sqrt(
                (user_pos["x"] - x) ** 2 + (user_pos["y"] - y) ** 2
            )

            if not member.can_receive_experience(int(distance)):
                continue

            # Calculate experience share using VB6 formula
            user_level = get_user_level_func(member.user_id)
            if user_level:
                exp_share = total_exp * (user_level ** LEVEL_EXPONENT) / self.sum_elevated_levels
                exp_share = math.floor(exp_share)  # VB6 uses Fix()

                member.add_experience(exp_share)
                distributed_exp[member.user_id] = exp_share

        return distributed_exp

    def update_member_level(self, user_id: int, new_level: int) -> bool:
        """Update member's level and recalculate elevated levels.

        Args:
            user_id: User ID to update
            new_level: New level of the user

        Returns:
            True if updated successfully, False if user not in party
        """
        member = self.get_member(user_id)
        if not member:
            return False

        # Remove old contribution
        self.sum_elevated_levels -= member.level ** LEVEL_EXPONENT

        # Update level
        member.level = new_level

        # Add new contribution
        self.sum_elevated_levels += member.level ** LEVEL_EXPONENT

        return True

    def transfer_leadership(self, new_leader_id: int) -> bool:
        """Transfer leadership to another member.

        Args:
            new_leader_id: User ID to make new leader

        Returns:
            True if transferred successfully, False if user not in party
        """
        if new_leader_id not in self.members:
            return False

        self.leader_id = new_leader_id
        self.leader_username = self.members[new_leader_id].username
        return True

    def get_online_members(self) -> list[PartyMember]:
        """Get list of online members."""
        return [member for member in self.members.values() if member.is_online]

    def set_member_online_status(self, user_id: int, is_online: bool) -> bool:
        """Set online status of a member.

        Args:
            user_id: User ID to update
            is_online: New online status

        Returns:
            True if updated successfully, False if user not in party
        """
        member = self.get_member(user_id)
        if not member:
            return False

        member.is_online = is_online
        if is_online:
            member.last_seen = time.time()

        return True


@dataclass
class PartyInvitation:
    """Represents a party invitation."""
    party_id: int
    inviter_id: int
    inviter_username: str
    target_id: int
    target_username: str
    created_at: float = field(default_factory=time.time)

    @property
    def is_expired(self) -> bool:
        """Check if invitation has expired (30 seconds timeout)."""
        return time.time() - self.created_at > 30
