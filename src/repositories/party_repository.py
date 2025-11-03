"""Repository for Party System persistence in Redis.

Handles storage and retrieval of parties, memberships, and invitations.
"""

# mypy: disable-error-code="misc,no-any-return"
# Redis operations return Any types which cause mypy warnings

import json
import time
from typing import TYPE_CHECKING, cast

from src.models.party import Party, PartyInvitation, PartyMember

if TYPE_CHECKING:
    from src.utils.redis_client import RedisClient


class PartyRepository:
    """Repository for party data persistence using Redis."""

    # Redis key patterns
    PARTY_KEY = "party:{party_id}"
    PARTY_MEMBERS_KEY = "party:{party_id}:members"
    PARTY_INDEX_KEY = "party:index"  # Set of all party IDs
    USER_PARTY_KEY = "user:{user_id}:party"  # Current party of user
    INVITATIONS_KEY = "party_invitations:{target_id}"  # Pending invitations for user
    NEXT_PARTY_ID_KEY = "party:next_id"  # Auto-incrementing party ID
    ALL_PARTIES_KEY = "parties:all"  # Hash of all parties

    # Constants
    INVITATION_TIMEOUT = 30  # seconds
    MAX_PARTY_ID = 999999  # Maximum party ID before reset

    def __init__(self, redis_client: RedisClient) -> None:
        """Initialize repository with Redis client.

        Args:
            redis_client: Redis client instance
        """
        self.redis = redis_client

    async def initialize(self) -> None:
        """Initialize repository - create next party ID if not exists."""
        exists = await self.redis.redis.exists(self.NEXT_PARTY_ID_KEY)
        if not exists:
            await self.redis.redis.set(self.NEXT_PARTY_ID_KEY, 1)

    async def get_next_party_id(self) -> int:
        """Get next available party ID.

        Returns:
            int: The next party ID.
        """
        party_id = cast(int, await self.redis.redis.incr(self.NEXT_PARTY_ID_KEY))
        if party_id > self.MAX_PARTY_ID:
            # Reset to 1 if we exceed maximum
            await self.redis.redis.set(self.NEXT_PARTY_ID_KEY, 1)
            party_id = 1
        return party_id

    async def save_party(self, party: Party) -> None:
        """Save complete party data to Redis."""
        pipe = self.redis.redis.pipeline()

        # Save party metadata
        party_data = {
            "party_id": party.party_id,
            "leader_id": party.leader_id,
            "leader_username": party.leader_username,
            "created_at": party.created_at,
            "total_exp_earned": party.total_exp_earned,
            "sum_elevated_levels": party.sum_elevated_levels,
            "member_count": party.member_count,
        }

        # Save to main party key and hash
        pipe.hset(self.ALL_PARTIES_KEY, str(party.party_id), json.dumps(party_data))
        pipe.set(self.PARTY_KEY.format(party_id=party.party_id), json.dumps(party_data))

        # Save each member
        for member in party.members.values():
            member_data = {
                "user_id": member.user_id,
                "username": member.username,
                "level": member.level,
                "accumulated_exp": member.accumulated_exp,
                "is_online": member.is_online,
                "last_seen": member.last_seen,
            }
            pipe.hset(
                self.PARTY_MEMBERS_KEY.format(party_id=party.party_id),
                str(member.user_id),
                json.dumps(member_data),
            )

            # Update user's current party
            pipe.set(self.USER_PARTY_KEY.format(user_id=member.user_id), party.party_id)

        # Add to party index
        pipe.sadd(self.PARTY_INDEX_KEY, party.party_id)

        await pipe.execute()

    async def get_party(self, party_id: int) -> Party | None:
        """Load party from Redis by ID.

        Returns:
            Party | None: The party if found, None otherwise.
        """
        # Get party metadata
        party_json = await self.redis.redis.get(self.PARTY_KEY.format(party_id=party_id))
        if not party_json:
            return None

        party_data = json.loads(party_json)

        # Get all members
        members_json = await self.redis.redis.hgetall(
            self.PARTY_MEMBERS_KEY.format(party_id=party_id)
        )

        members: dict[int, PartyMember] = {}
        for member_json in members_json.values():
            member_data = json.loads(member_json)
            member = PartyMember(
                user_id=member_data["user_id"],
                username=member_data["username"],
                level=member_data["level"],
                accumulated_exp=member_data["accumulated_exp"],
                is_online=member_data["is_online"],
                last_seen=member_data["last_seen"],
            )
            members[member.user_id] = member

        # Reconstruct party
        party = Party(
            party_id=party_data["party_id"],
            leader_id=party_data["leader_id"],
            leader_username=party_data["leader_username"],
        )
        party.members = members
        party.created_at = party_data["created_at"]
        party.total_exp_earned = party_data["total_exp_earned"]
        party.sum_elevated_levels = party_data["sum_elevated_levels"]

        return party

    async def get_user_party(self, user_id: int) -> Party | None:
        """Get the party that user is currently in.

        Returns:
            Party | None: The user's party if found, None otherwise.
        """
        party_id = await self.redis.redis.get(self.USER_PARTY_KEY.format(user_id=user_id))
        if not party_id:
            return None

        return await self.get_party(int(party_id))

    async def delete_party(self, party_id: int) -> None:
        """Delete party and all associated data."""
        pipe = self.redis.redis.pipeline()

        # Get members to clean up their party references
        members_json = await self.redis.redis.hgetall(
            self.PARTY_MEMBERS_KEY.format(party_id=party_id)
        )

        for member_json in members_json.values():
            member_data = json.loads(member_json)
            pipe.delete(self.USER_PARTY_KEY.format(user_id=member_data["user_id"]))

        # Delete party data
        pipe.delete(self.PARTY_KEY.format(party_id=party_id))
        pipe.delete(self.PARTY_MEMBERS_KEY.format(party_id=party_id))
        pipe.hdel(self.ALL_PARTIES_KEY, str(party_id))
        pipe.srem(self.PARTY_INDEX_KEY, party_id)

        await pipe.execute()

    async def update_member(self, party_id: int, member: PartyMember) -> None:
        """Update a single member's data."""
        member_data = {
            "user_id": member.user_id,
            "username": member.username,
            "level": member.level,
            "accumulated_exp": member.accumulated_exp,
            "is_online": member.is_online,
            "last_seen": member.last_seen,
        }

        await self.redis.redis.hset(
            self.PARTY_MEMBERS_KEY.format(party_id=party_id),
            str(member.user_id),
            json.dumps(member_data),
        )

    async def remove_member_from_party(self, party_id: int, user_id: int) -> None:
        """Remove a member from party data."""
        pipe = self.redis.redis.pipeline()

        # Remove from members
        pipe.hdel(self.PARTY_MEMBERS_KEY.format(party_id=party_id), str(user_id))

        # Remove user's party reference
        pipe.delete(self.USER_PARTY_KEY.format(user_id=user_id))

        await pipe.execute()

    async def add_member_to_party(self, party_id: int, member: PartyMember) -> None:
        """Add a member to existing party."""
        member_data = {
            "user_id": member.user_id,
            "username": member.username,
            "level": member.level,
            "accumulated_exp": member.accumulated_exp,
            "is_online": member.is_online,
            "last_seen": member.last_seen,
        }

        pipe = self.redis.redis.pipeline()

        # Add to members
        pipe.hset(
            self.PARTY_MEMBERS_KEY.format(party_id=party_id),
            str(member.user_id),
            json.dumps(member_data),
        )

        # Update user's party reference
        pipe.set(self.USER_PARTY_KEY.format(user_id=member.user_id), party_id)

        # Update party metadata
        current_data = await self.redis.redis.get(self.PARTY_KEY.format(party_id=party_id))
        if current_data:
            party_data = json.loads(current_data)
            party_data["member_count"] = (
                len(
                    await self.redis.redis.hgetall(self.PARTY_MEMBERS_KEY.format(party_id=party_id))
                )
                + 1
            )  # +1 for the new member

            pipe.set(self.PARTY_KEY.format(party_id=party_id), json.dumps(party_data))
            pipe.hset(self.ALL_PARTIES_KEY, str(party_id), json.dumps(party_data))

        await pipe.execute()

    async def get_all_parties(self) -> list[int]:
        """Get list of all party IDs.

        Returns:
            list[int]: List of all active party IDs.
        """
        party_ids = await self.redis.redis.smembers(self.PARTY_INDEX_KEY)
        return [int(pid) for pid in party_ids]

    async def get_party_count(self) -> int:
        """Get total number of active parties.

        Returns:
            int: Number of active parties.
        """
        return await self.redis.redis.scard(self.PARTY_INDEX_KEY)

    async def save_invitation(self, invitation: PartyInvitation) -> None:
        """Save party invitation."""
        invitation_data = {
            "party_id": invitation.party_id,
            "inviter_id": invitation.inviter_id,
            "inviter_username": invitation.inviter_username,
            "target_id": invitation.target_id,
            "target_username": invitation.target_username,
            "created_at": invitation.created_at,
        }

        await self.redis.redis.hset(
            self.INVITATIONS_KEY.format(target_id=invitation.target_id),
            str(invitation.party_id),
            json.dumps(invitation_data),
        )

    async def get_invitation(self, target_id: int, party_id: int) -> PartyInvitation | None:
        """Get specific invitation for target user.

        Returns:
            PartyInvitation | None: The invitation if found, None otherwise.
        """
        invitation_json = await self.redis.redis.hget(
            self.INVITATIONS_KEY.format(target_id=target_id), str(party_id)
        )

        if not invitation_json:
            return None

        invitation_data = json.loads(invitation_json)
        invitation = PartyInvitation(
            party_id=invitation_data["party_id"],
            inviter_id=invitation_data["inviter_id"],
            inviter_username=invitation_data["inviter_username"],
            target_id=invitation_data["target_id"],
            target_username=invitation_data["target_username"],
        )
        invitation.created_at = invitation_data["created_at"]

        return invitation

    async def get_user_invitations(self, target_id: int) -> list[PartyInvitation]:
        """Get all pending invitations for a user.

        Returns:
            list[PartyInvitation]: List of pending invitations.
        """
        invitations_json = await self.redis.redis.hgetall(
            self.INVITATIONS_KEY.format(target_id=target_id)
        )

        invitations = []
        current_time = time.time()

        for invitation_json in invitations_json.values():
            invitation_data = json.loads(invitation_json)

            # Check if expired (30 seconds timeout)
            if current_time - invitation_data["created_at"] > self.INVITATION_TIMEOUT:
                # Remove expired invitation
                await self.remove_invitation(
                    invitation_data["target_id"], invitation_data["party_id"]
                )
                continue

            invitation = PartyInvitation(
                party_id=invitation_data["party_id"],
                inviter_id=invitation_data["inviter_id"],
                inviter_username=invitation_data["inviter_username"],
                target_id=invitation_data["target_id"],
                target_username=invitation_data["target_username"],
            )
            invitation.created_at = invitation_data["created_at"]
            invitations.append(invitation)

        return invitations

    async def remove_invitation(self, target_id: int, party_id: int) -> None:
        """Remove a specific invitation."""
        await self.redis.redis.hdel(self.INVITATIONS_KEY.format(target_id=target_id), str(party_id))

    async def clear_user_invitations(self, target_id: int) -> None:
        """Clear all invitations for a user."""
        await self.redis.redis.delete(self.INVITATIONS_KEY.format(target_id=target_id))

    @staticmethod
    async def cleanup_expired_invitations() -> int:
        """Remove all expired invitations and return count cleaned.

        Returns:
            int: Number of invitations cleaned.
        """
        # This would require scanning all invitation keys
        # For now, we'll clean up when retrieving invitations
        return 0

    async def update_party_metadata(self, party: Party) -> None:
        """Update only party metadata (not members)."""
        party_data = {
            "party_id": party.party_id,
            "leader_id": party.leader_id,
            "leader_username": party.leader_username,
            "created_at": party.created_at,
            "total_exp_earned": party.total_exp_earned,
            "sum_elevated_levels": party.sum_elevated_levels,
            "member_count": party.member_count,
        }

        pipe = self.redis.redis.pipeline()
        pipe.set(self.PARTY_KEY.format(party_id=party.party_id), json.dumps(party_data))
        pipe.hset(self.ALL_PARTIES_KEY, str(party.party_id), json.dumps(party_data))

        await pipe.execute()
